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
    def __init__(self):
        self.chunks: List[Dict] = []
        self.vectors: Optional[np.ndarray] = None   # (n, dim) 语义向量
        self.tfidf = _TfidfEngine()
        self.engine_mode: str = "init"              # embedding / tfidf
        self.ready: bool = False
        self.build_time: float = 0.0
        self._query_cache: Dict[str, np.ndarray] = {}  # 查询向量缓存(评委高频重复提问秒回)

    # ---------- 构建 ----------
    async def build(self):
        t0 = time.time()
        md_path = settings.KNOWLEDGE_MD
        json_path = str(Path(settings.FRONTEND_DIR) / "assets" / "knowledge.json")
        self.chunks = _parse_markdown_chunks(md_path) + _parse_json_chunks(json_path)

        # 合并管理后台维护的知识条目(已发布状态)——知识库管理功能真实生效
        try:
            from sqlalchemy import select
            from app.core.database import async_session
            from app.models.models import KnowledgeItem
            async with async_session() as db:
                rows = (await db.execute(
                    select(KnowledgeItem).where(KnowledgeItem.status == "published")
                )).scalars().all()
            for r in rows:
                self.chunks.append({
                    "title": r.title,
                    "content": f"{r.title}\n{r.content}",
                    "source": f"ADMIN-{r.id}",
                })
            if rows:
                print(f"[RAG] 合并后台知识条目 {len(rows)} 条")
        except Exception as e:
            print(f"[RAG] 后台知识条目加载跳过: {e}")

        if not self.chunks:
            raise RuntimeError("知识库为空,请检查知识库文件路径")

        docs = [f"{c['title']}\n{c['content']}" for c in self.chunks]
        # TF-IDF始终构建(兜底+混合加权)
        self.tfidf.fit(docs)

        # 尝试加载/构建语义向量
        self.vectors = await self._load_or_embed(docs)
        self.engine_mode = "embedding" if self.vectors is not None else "tfidf"
        self.build_time = time.time() - t0
        self.ready = True
        print(f"[RAG] 知识库构建完成: {len(self.chunks)}块 | 引擎:{self.engine_mode} | 耗时:{self.build_time:.1f}s")

    def _source_hash(self, docs: List[str]) -> str:
        h = hashlib.md5()
        for d in docs:
            h.update(d.encode("utf-8"))
        return h.hexdigest()

    async def _embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """调用DashScope embedding,失败返回None"""
        if not settings.LLM_API_KEY:
            return None
        url = f"{settings.LLM_BASE_URL}/v1/embeddings"
        headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}"}
        out = []
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                B = 10  # DashScope单批上限
                for i in range(0, len(texts), B):
                    payload = {"model": settings.EMBEDDING_MODEL,
                               "input": texts[i:i + B],
                               "dimensions": settings.EMBEDDING_DIM}
                    r = await client.post(url, headers=headers, json=payload)
                    if r.status_code != 200:
                        print(f"[RAG] Embedding失败({r.status_code}),降级TF-IDF")
                        return None
                    data = r.json()["data"]
                    data.sort(key=lambda x: x["index"])
                    out.extend([d["embedding"] for d in data])
            return out
        except Exception as e:
            print(f"[RAG] Embedding异常:{e},降级TF-IDF")
            return None

    async def _load_or_embed(self, docs: List[str]) -> Optional[np.ndarray]:
        cache = Path(settings.VECTOR_CACHE)
        src_hash = self._source_hash(docs)
        if cache.exists():
            try:
                z = np.load(cache, allow_pickle=False)
                if z["hash"].tobytes().decode() == src_hash:
                    return z["vectors"].astype(np.float32)
            except Exception:
                pass
        vecs = await self._embed_batch(docs)
        if vecs is None:
            return None
        arr = np.asarray(vecs, dtype=np.float32)
        arr = arr / np.maximum(np.linalg.norm(arr, axis=1, keepdims=True), 1e-9)
        np.savez(cache, vectors=arr, hash=np.frombuffer(src_hash.encode(), dtype=np.uint8))
        return arr

    # ---------- 检索 ----------
    async def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        if not self.ready:
            return []
        top_k = top_k or settings.RAG_TOP_K
        docs = [f"{c['title']}\n{c['content']}" for c in self.chunks]

        # TF-IDF分数(始终可得)
        tfidf_scores = self.tfidf.query(query, top_k)

        # 语义分数
        emb_scores = np.zeros(len(self.chunks), dtype=np.float32)
        if self.vectors is not None and settings.LLM_API_KEY:
            q = self._query_cache.get(query)
            if q is None:
                qv = await self._embed_batch([query])
                if qv is not None:
                    q = np.asarray(qv[0], dtype=np.float32)
                    q = q / max(np.linalg.norm(q), 1e-9)
                    if len(self._query_cache) < 500:
                        self._query_cache[query] = q
            if q is not None:
                emb_scores = self.vectors @ q

        # 关键词命中加权(景点名/别名精确命中强信号)
        kw_boost = np.zeros(len(self.chunks), dtype=np.float32)
        q_clean = re.sub(r"[？?!！。,，、\s]", "", query)
        for i, c in enumerate(self.chunks):
            title_clean = re.sub(r"[（(].*?[)）]", "", c["title"])
            if len(title_clean) >= 2 and title_clean in q_clean:
                kw_boost[i] = 1.0

        # 混合:语义0.6 + TFIDF0.25 + 关键词0.15
        final = 0.6 * emb_scores + 0.25 * tfidf_scores + 0.15 * kw_boost
        if self.vectors is None:  # 纯TF-IDF模式
            final = 0.75 * tfidf_scores + 0.25 * kw_boost

        idx = np.argsort(-final)[:top_k]
        results = []
        for i in idx:
            if final[i] < settings.RAG_SCORE_THRESHOLD and kw_boost[i] == 0:
                continue
            results.append({
                "title": self.chunks[i]["title"],
                "content": self.chunks[i]["content"],
                "score": round(float(final[i]), 4),
                "source": self.chunks[i]["source"],
            })
        return results

    @property
    def status(self) -> Dict:
        return {"ready": self.ready, "chunks": len(self.chunks),
                "engine": self.engine_mode, "build_time_s": round(self.build_time, 2)}


rag_service = RagService()
