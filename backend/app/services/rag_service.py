"""
RAG 检索增强生成服务
--------------------
双引擎设计:
  1. 语义向量引擎:DashScope text-embedding-v3 + numpy余弦相似度(主)
  2. 关键词TF-IDF引擎:jieba分词(无网络/无Key时自动降级,保证系统永不瘫痪)

知识来源:
  - 知识库/灵山胜境完整知识库.md (按标题层级切块)
  - design/lingshan-guide/assets/knowledge.json (22景点+3路线结构化数据)
"""
import hashlib
import json
import re
import time
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
import httpx

from app.core.config import settings


# ============================================================
# 知识切块
# ============================================================
def _parse_markdown_chunks(md_path: str) -> List[Dict]:
    """按Markdown标题层级将知识库切成语义块"""
    text = Path(md_path).read_text(encoding="utf-8")
    chunks = []
    # 以 ###/#### 标题作为切块边界,保留标题上下文
    pattern = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
    matches = list(pattern.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        # 去掉Markdown表格修饰,压缩为纯文本(利于embedding与prompt)
        content = re.sub(r"\|[-\s|]+\|", "", content)
        content = re.sub(r"\s*\n\s*", "\n", content).strip()
        if len(content) < 20:
            continue
        if len(content) > 1200:  # 超长块二次切分(按段落)
            paras = [p.strip() for p in content.split("\n\n") if p.strip()]
            buf = ""
            part = 1
            for p in paras:
                if len(buf) + len(p) > 1000 and buf:
                    chunks.append({"title": f"{title}({part})", "content": buf.strip(),
                                   "source": "知识库.md"})
                    part += 1
                    buf = p
                else:
                    buf += "\n\n" + p
            if buf.strip():
                chunks.append({"title": f"{title}({part})", "content": buf.strip(),
                               "source": "知识库.md"})
        else:
            chunks.append({"title": title, "content": content, "source": "知识库.md"})
    return chunks


def _parse_json_chunks(json_path: str) -> List[Dict]:
    """结构化景点/路线数据转为知识块"""
    p = Path(json_path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    chunks = []
    for sid, s in (data.get("spots") or {}).items():
        content = (f"景点:{s.get('name','')}\n介绍:{s.get('intro','')}\n"
                   f"文化内涵:{s.get('culture','')}\n亮点:{'、'.join(s.get('highlights') or [])}\n"
                   f"游览提示:{s.get('tips','')}")
        chunks.append({"title": s.get("name", sid), "content": content, "source": sid})
    for i, r in enumerate(data.get("routes") or []):
        content = (f"游览路线{i+1}:{r.get('name','')}\n时长:{r.get('duration','')} | "
                   f"适合人群:{r.get('target','')}\n路线:{' → '.join(r.get('route') or [])}\n"
                   f"讲解重点:{'；'.join(r.get('focus') or [])}\n特色体验:{'、'.join(r.get('experiences') or [])}")
        chunks.append({"title": f"路线:{r.get('name','')}", "content": content, "source": f"ROUTE-{i+1}"})
    bi = data.get("baseInfo") or {}
    for key, label in [("ticket", "门票信息"), ("freeTicket", "免票政策"), ("openTime", "开放时间"),
                       ("transport", "交通指南"), ("dining", "餐饮信息"), ("accommodation", "住宿推荐"),
                       ("fiveBuddhas", "五方五佛"), ("zenStory", "拈花微笑典故"),
                       ("threeTraditions", "佛教三大语系"), ("capacity", "景区承载量")]:
        if bi.get(key):
            chunks.append({"title": label, "content": f"{label}:{bi[key]}", "source": f"BASE-{key}"})
    return chunks


# ============================================================
# TF-IDF 离线引擎
# ============================================================
class _TfidfEngine:
    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.idf: Optional[np.ndarray] = None
        self.matrix: Optional[np.ndarray] = None  # (n_chunks, n_vocab)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        import jieba
        return [w for w in jieba.lcut(text.lower()) if len(w.strip()) >= 1 and not w.isspace()]

    def fit(self, docs: List[str]):
        tokenized = [self._tokenize(d) for d in docs]
        vocab = {}
        for toks in tokenized:
            for t in set(toks):
                vocab.setdefault(t, len(vocab))
        self.vocab = vocab
        n, v = len(tokenized), len(vocab)
        tf = np.zeros((n, v), dtype=np.float32)
        df = np.zeros(v, dtype=np.float32)
        for i, toks in enumerate(tokenized):
            for t in toks:
                tf[i, vocab[t]] += 1
            for t in set(toks):
                df[vocab[t]] += 1
        tf = tf / np.maximum(tf.sum(axis=1, keepdims=True), 1e-9)
        self.idf = np.log((n + 1) / (df + 1)) + 1
        self.matrix = tf * self.idf
        # L2归一化
        self.matrix = self.matrix / np.maximum(
            np.linalg.norm(self.matrix, axis=1, keepdims=True), 1e-9)

    def query(self, text: str, top_k: int) -> np.ndarray:
        toks = self._tokenize(text)
        v = len(self.vocab)
        qv = np.zeros(v, dtype=np.float32)
        for t in toks:
            if t in self.vocab:
                qv[self.vocab[t]] += 1
        if qv.sum() == 0:
            return np.zeros(self.matrix.shape[0], dtype=np.float32)
        qv = qv / qv.sum() * self.idf
        qv = qv / max(np.linalg.norm(qv), 1e-9)
        return self.matrix @ qv


# ============================================================
# RAG 服务主体
# ============================================================
class RagService:
    """Publish complete immutable-by-convention generations; validate SQL revision on every read."""
    def __init__(self):
        import asyncio
        self._snapshot = None
        self._query_cache = {}
        self._build_lock = asyncio.Lock()
        self.build_time = 0.0

    @property
    def chunks(self):
        return [dict(c) for c in self._snapshot['chunks']] if self._snapshot else []

    @property
    def vectors(self):
        return self._snapshot['vectors'] if self._snapshot else None

    @property
    def ready(self):
        return self._snapshot is not None

    @property
    def engine_mode(self):
        return self._snapshot['engine'] if self._snapshot else 'init'

    def _identity(self):
        return f'{settings.LLM_BASE_URL.rstrip("/")}|{settings.EMBEDDING_MODEL}|{settings.EMBEDDING_DIM}'

    def _source_hash(self, docs):
        return hashlib.sha256(json.dumps([self._identity(), docs],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

    async def _state(self):
        from app.core.database import async_session
        from app.models.models import KnowledgeRevision
        async with async_session() as db:
            row = await db.get(KnowledgeRevision,1)
            return (row.value,row.chunk_size,row.overlap) if row else (0,800,80)

    async def _collect(self):
        from starlette.concurrency import run_in_threadpool
        from sqlalchemy import select
        from app.core.database import async_session
        from app.models.models import KnowledgeItem
        def read_files():
            return _parse_markdown_chunks(settings.KNOWLEDGE_MD) + _parse_json_chunks(str(Path(settings.FRONTEND_DIR)/'assets/knowledge.json'))
        chunks = await run_in_threadpool(read_files)
        async with async_session() as db:
            rows=(await db.execute(select(KnowledgeItem).where(KnowledgeItem.status=='published').order_by(KnowledgeItem.id))).scalars().all()
            chunks += [{'title':r.title,'content':f'{r.title}\n{r.content}','source':f'ADMIN-{r.id}'} for r in rows]
        return chunks

    @staticmethod
    def _prepare(chunks,state):
        _,size,overlap=state
        if not 0<=overlap<size:
            raise ValueError('invalid chunk settings')
        records=[]
        for item in chunks:
            text=item['content']
            start=0
            while start < len(text):
                end=min(start+size,len(text))
                content=text[start:end].strip()
                if content:
                    chunk=dict(item,content=content)
                    chunk['chunk_id']=hashlib.sha256(f'{item["source"]}|{item["title"]}|{start}|{content}'.encode()).hexdigest()[:24]
                    records.append(chunk)
                if end==len(text): break
                start=end-overlap
        docs=[f'{c["title"]}\n{c["content"]}' for c in records]
        tfidf=_TfidfEngine()
        tfidf.fit(docs)
        return records,docs,tfidf

    async def build(self):
        from starlette.concurrency import run_in_threadpool
        async with self._build_lock:
            t0=time.monotonic()
            for _ in range(3):
                state=await self._state()
                identity=self._identity()
                chunks,docs,tfidf=await run_in_threadpool(self._prepare,await self._collect(),state)
                vectors=await self._load_or_embed(docs)
                if state!=await self._state() or identity!=self._identity():
                    continue
                if vectors is not None: vectors.setflags(write=False)
                self._snapshot={'state':state,'identity':identity,'chunks':tuple(chunks),'tfidf':tfidf,'vectors':vectors,'engine':'embedding' if vectors is not None else 'tfidf'}
                self._query_cache.clear()
                self.build_time=time.monotonic()-t0
                return
            raise RuntimeError('knowledge changed repeatedly during rebuild; retry')

    async def _embed_batch(self,texts):
        if not settings.LLM_API_KEY or settings.DEMO_MODE or not texts:
            return None
        base=settings.LLM_BASE_URL.rstrip('/')
        url=(base if base.endswith('/v1') else base+'/v1')+'/embeddings'
        out=[]
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for start in range(0,len(texts),10):
                    batch=texts[start:start+10]
                    r=await client.post(url,headers={'Authorization':f'Bearer {settings.LLM_API_KEY}'},json={'model':settings.EMBEDDING_MODEL,'input':batch,'dimensions':settings.EMBEDDING_DIM})
                    r.raise_for_status()
                    data=sorted(r.json()['data'],key=lambda x:x['index'])
                    if [d['index'] for d in data]!=list(range(len(batch))): return None
                    out.extend(d['embedding'] for d in data)
            arr=np.asarray(out,dtype=np.float32)
            if arr.shape!=(len(texts),settings.EMBEDDING_DIM) or not np.isfinite(arr).all(): return None
            return out
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            return None

    async def _load_or_embed(self,docs):
        from starlette.concurrency import run_in_threadpool
        import os,uuid
        cache=Path(settings.VECTOR_CACHE)
        digest=self._source_hash(docs)
        def load():
            if not cache.exists(): return None
            try:
                with np.load(cache,allow_pickle=False) as z:
                    arr=z['vectors'].astype(np.float32)
                    if z['hash'].tobytes().decode()==digest and arr.shape==(len(docs),settings.EMBEDDING_DIM) and np.isfinite(arr).all():
                        return arr
            except (OSError,ValueError,KeyError,UnicodeError): pass
            cache.unlink(missing_ok=True)
            return None
        cached=await run_in_threadpool(load)
        if cached is not None: return cached
        values=await self._embed_batch(docs)
        if values is None: return None
        arr=np.asarray(values,dtype=np.float32)
        if arr.shape!=(len(docs),settings.EMBEDDING_DIM) or not np.isfinite(arr).all(): return None
        arr=arr/np.maximum(np.linalg.norm(arr,axis=1,keepdims=True),1e-9)
        def save():
            cache.parent.mkdir(parents=True,exist_ok=True)
            temp=cache.with_name(cache.name+'.'+uuid.uuid4().hex+'.npz')
            try:
                np.savez(temp,vectors=arr,hash=np.frombuffer(digest.encode(),dtype=np.uint8))
                os.replace(temp,cache)
            finally: temp.unlink(missing_ok=True)
        await run_in_threadpool(save)
        return arr

    @staticmethod
    def _rank(snapshot,query,qvec,top_k):
        chunks=snapshot['chunks']
        if not chunks: return []
        lexical=snapshot['tfidf'].query(query,top_k)
        semantic=np.zeros(len(chunks),dtype=np.float32)
        if qvec is not None: semantic=snapshot['vectors']@qvec
        boost=np.zeros(len(chunks),dtype=np.float32)
        clean=re.sub(r'[？?!！。,，、\s]','',query)
        for i,c in enumerate(chunks):
            title=re.sub(r'[（(].*?[)）]','',c['title'])
            if len(title)>=2 and title in clean: boost[i]=1
        scores=0.6*semantic+0.25*lexical+0.15*boost if qvec is not None else 0.75*lexical+0.25*boost
        return [dict(chunks[i],score=round(float(scores[i]),4),revision=snapshot['state'][0]) for i in np.argsort(-scores)[:top_k] if scores[i]>=settings.RAG_SCORE_THRESHOLD or boost[i]>0]

    async def retrieve(self,query,top_k=None):
        from starlette.concurrency import run_in_threadpool
        for _ in range(3):
            state=await self._state()
            snapshot=self._snapshot
            if snapshot is None or snapshot['state']!=state or snapshot['identity']!=self._identity():
                await self.build()
                snapshot=self._snapshot
            qvec=None
            if snapshot['vectors'] is not None and settings.LLM_API_KEY and not settings.DEMO_MODE:
                key=(snapshot['identity'],snapshot['state'],query)
                qvec=self._query_cache.get(key)
                if qvec is None:
                    values=await self._embed_batch([query])
                    if values is not None:
                        qvec=np.asarray(values[0],dtype=np.float32)
                        if qvec.shape!=(settings.EMBEDDING_DIM,) or not np.isfinite(qvec).all(): qvec=None
                        else:
                            qvec=qvec/max(np.linalg.norm(qvec),1e-9)
                            if self._snapshot is snapshot:
                                if len(self._query_cache)>=500: self._query_cache.pop(next(iter(self._query_cache)))
                                self._query_cache[key]=qvec
            results=await run_in_threadpool(self._rank,snapshot,query,qvec,top_k or settings.RAG_TOP_K)
            if await self._state()==snapshot['state'] and snapshot['identity']==self._identity():
                return results
        raise RuntimeError('knowledge changed repeatedly during retrieval; retry')

    @property
    def status(self):
        return {'ready':self.ready,'chunks':len(self._snapshot['chunks']) if self.ready else 0,'engine':self.engine_mode,'revision':self._snapshot['state'][0] if self.ready else None,'embedding_model':settings.EMBEDDING_MODEL if self.vectors is not None else None,'build_time_s':round(self.build_time,2)}


rag_service=RagService()
