"""
对话编排服务 - 全链路流式管线
游客提问 → RAG检索 → LLM流式生成 → 按句切分 → 逐句TTS+口型时间轴 → SSE推送
延迟必须实际测量；承接语音频不能当作模型内容首音频指标。
"""
import asyncio
import re
import time
import uuid
import logging
from contextlib import aclosing
import anyio
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy import select,update

from app.core.database import async_session
from app.core.config import settings
from app.models.models import ChatMessage, ChatSession, TouristFeedback
from app.services.llm_service import llm_service, parse_emotion, strip_emotion
from app.services.rag_service import rag_service
from app.services.sentiment import analyze_sentiment
from app.services.tts_service import tts_service
from app.core.evidence import model_trace, CitationFilter

SENTENCE_END = re.compile(r"([。！？!?；;])")
CLAUSE_END = re.compile(r"([。！？!?；;，,、])")
VALID_CHAR = re.compile(r"[一-鿿a-zA-Z0-9]")

# 承接语池:提问瞬间先行开口(音频有缓存,二次触发合成≈0ms),
# 数字人"秒开口",LLM生成期间的等待感被自然消解
PRELUDE_PHRASES = [
    "阿弥陀佛,且听小仙为您细细道来。",
    "善哉善哉,这个问题问得好。",
    "阿弥陀佛,小仙这便为您讲解。",
    "善哉,容小仙为您介绍一二。",
    "阿弥陀佛,您可算是问对人了。",
    "善哉善哉,且听小仙慢慢说来。",
]


class ChatService:
    """RAG + LLM + TTS 编排"""

    # ---------------- 会话持久化 ----------------
    async def _ensure_session(self, tourist_id: str) -> int:
        async with async_session() as db:
            q = select(ChatSession).where(ChatSession.tourist_id == tourist_id) \
                .order_by(ChatSession.id.desc()).limit(1)
            row = (await db.execute(q)).scalar_one_or_none()
            if row:
                return row.id
            s = ChatSession(tourist_id=tourist_id)
            db.add(s)
            await db.commit()
            return s.id

    async def _save_message(self, session_id: int, role: str, content: str,
                            intent: Optional[str] = None, outcome: str = 'completed', request_id: str | None = None):
        async with async_session() as db:
            db.add(ChatMessage(session_id=session_id, role=role,
                               content=content, intent=intent, outcome=outcome, request_id=request_id))
            await db.commit()

    async def _log_feedback(self, tourist_id: str, question: str, answer: str):
        sentiment, score = analyze_sentiment(question)
        async with async_session() as db:
            row=TouristFeedback(tourist_id=tourist_id, question=question,
                                   answer=answer[:500], satisfaction=None,
                                   sentiment=sentiment)
            db.add(row)
            await db.commit()
            return row.id

    async def get_history(self, tourist_id: str, limit: int = 6, model_context: bool = False) -> List[Dict]:
        async with async_session() as db:
            q = select(ChatSession).where(ChatSession.tourist_id == tourist_id) \
                .order_by(ChatSession.id.desc()).limit(1)
            session = (await db.execute(q)).scalar_one_or_none()
            if not session:
                return []
            q2 = select(ChatMessage).where(ChatMessage.session_id == session.id) \
                .order_by(ChatMessage.id.desc()).limit(limit)
            if model_context:
                q2=q2.where(ChatMessage.outcome.in_(['completed','refused']))
            rows = (await db.execute(q2)).scalars().all()
            return [{"role": r.role, "content": r.content, 'outcome':r.outcome, 'request_id':r.request_id} for r in reversed(rows)]

    # ---------------- 意图识别 ----------------
    @staticmethod
    def detect_intent(query: str) -> str:
        intents = {
            "route": ["路线", "推荐", "怎么玩", "安排", "计划", "攻略"],
            "ticket": ["门票", "价格", "多少钱", "票价", "预约"],
            "time": ["开放", "时间", "几点", "表演", "场次"],
            "traffic": ["交通", "怎么去", "公交", "地铁", "停车", "自驾"],
            "food": ["吃饭", "餐厅", "素斋", "美食", "小吃"],
            "hotel": ["住宿", "酒店", "住"],
            "scenic_spot": ["景点", "大佛", "梵宫", "九龙", "菩提", "坛城", "拈花"],
        }
        for key, kws in intents.items():
            if any(kw in query for kw in kws):
                return key
        return "general"

    async def stream_pipeline(self, query: str, tourist_id: str = 'guest', interest=None,
                              time_budget=None, companions=None, tts_enabled=True, request_id=None):
        """Bounded speech work; explicit partial/refused/cancelled outcomes; close upstream on exit."""
        started=time.monotonic()
        request_id=request_id or uuid.uuid4().hex
        session_id=await self._ensure_session(tourist_id)
        history=await self.get_history(tourist_id,model_context=True)
        await self._save_message(session_id,'user',query,outcome='generating',request_id=request_id)
        answer=''
        emotion='calm'
        status='failed'
        pending={}
        index=0
        feedback_id=None
        persisted=False
        sources=[]
        generation=None
        first_text_ms=None
        first_audio_ready_ms=None
        trace={'path':'not_started','model':None,'attempts':[],'switch_reason':None,'rejected_citations':0}
        trace_token=model_trace.set(trace)
        citation_filter=None

        async def synth(idx,text,prelude):
            nonlocal first_audio_ready_ms
            try:
                meta=await asyncio.wait_for(tts_service.synthesize(text),timeout=12)
                meta=tts_service.grant_audio(meta)
            except Exception:
                meta={'ok':False,'engine':'none','reason':'语音合成暂不可用'}
            if not prelude and meta.get('audio_url') and first_audio_ready_ms is None:
                first_audio_ready_ms=round((time.monotonic()-started)*1000,2)
            return {'type':'sentence','index':idx,'text':text,'prelude':prelude,'audio_url':meta.get('audio_url'),
                    'tts_ok':meta.get('ok',False),'visemes':meta.get('visemes',[]),'duration_ms':meta.get('duration_ms',0),
                    'engine':meta.get('engine','none'),'mouth_alignment':meta.get('mouth_alignment','unavailable'),'request_id':request_id}

        async def enqueue(text,prelude=False):
            nonlocal index
            if not tts_enabled or not VALID_CHAR.search(text): return
            if len(pending)>=4:
                oldest=next(iter(pending))
                yield await pending.pop(oldest)
            idx=-1 if prelude else index
            if not prelude: index+=1
            pending[idx]=asyncio.create_task(synth(idx,text,prelude))

        try:
            chunks=await rag_service.retrieve(query)
            sources=[{**{k:c[k] for k in ('title','source','score','content','chunk_id','revision','updated_at_kind') if k in c},
                      'updated_at':c.get('updated_at'),'citation_status':'retrieved_unverified','supports_answer':None} for c in chunks]
            citation_filter=CitationFilter(chunks)
            generation=rag_service.status.get('revision')
            yield {'type':'meta','intent':self.detect_intent(query),'engine':rag_service.engine_mode,'sources':sources,'knowledge_revision':generation,'request_id':request_id}
            if not chunks:
                answer='抱歉，本地景区知识库没有找到可靠依据，请换个问法或咨询景区工作人员。'
                status='refused'
                trace.update(path='no_evidence_refusal',switch_reason='no_retrieved_evidence')
                first_text_ms=round((time.monotonic()-started)*1000,2)
                yield {'type':'delta','text':answer,'request_id':request_id}
                async for evt in enqueue(answer): yield evt
            else:
                async for evt in enqueue(PRELUDE_PHRASES[hash(tourist_id+query)%len(PRELUDE_PHRASES)],True): yield evt
                if self.detect_intent(query) in ('ticket','time') or re.search('今天|实时|现在|最新',query):
                    answer='【时效提醒】资料更新时间未核实，以下内容不代表实时票价、开放或演出安排，请以景区官方公告为准。\n'
                    yield {'type':'delta','text':answer,'request_id':request_id,'notice':True}
                head=''
                resolved=False
                sentence=''
                async with aclosing(llm_service.stream_chat(query,chunks,history,interest,time_budget,companions)) as stream:
                    async for token in stream:
                        if not resolved:
                            head+=token
                            if head.startswith('[emotion:') and ']' in head:
                                emotion=parse_emotion(head)
                                token=strip_emotion(head)
                            elif '[emotion:'.startswith(head) or head.startswith('[emotion:') and len(head)<32:
                                continue
                            else: token=head
                            resolved=True
                            yield {'type':'emotion','emotion':emotion,'request_id':request_id}
                        token=citation_filter.feed(token)
                        if not token or first_text_ms is None and not token.strip(): continue
                        if first_text_ms is None: first_text_ms=round((time.monotonic()-started)*1000,2)
                        answer+=token
                        if len(answer)>6000: raise RuntimeError('answer limit')
                        sentence+=token
                        yield {'type':'delta','text':token,'request_id':request_id}
                        parts=SENTENCE_END.split(sentence)
                        while len(parts)>=2:
                            sent=parts.pop(0)+parts.pop(0)
                            async for evt in enqueue(sent.strip()): yield evt
                        sentence=''.join(parts)
                        if len(sentence)>160:
                            async for evt in enqueue(sentence[:160]): yield evt
                            sentence=sentence[160:]
                        while pending and pending[next(iter(pending))].done():
                            yield await pending.pop(next(iter(pending)))
                tail=citation_filter.feed(strip_emotion(head) if not resolved else '',final=True)
                if tail:
                    if first_text_ms is None and tail.strip(): first_text_ms=round((time.monotonic()-started)*1000,2)
                    answer+=tail; sentence+=tail
                    yield {'type':'delta','text':tail,'request_id':request_id}
                if first_text_ms is None: raise RuntimeError('empty final answer')
                async for evt in enqueue(sentence.strip()): yield evt
                if generation is not None and (await rag_service._state())[0]!=generation:
                    raise RuntimeError('knowledge changed during answer')
                status='completed'
            while pending:
                yield await pending.pop(next(iter(pending)))
        except (asyncio.CancelledError,GeneratorExit):
            status='cancelled'
            raise
        except Exception as exc:
            status='partial' if answer.strip() else 'failed'
            logging.getLogger(__name__).warning('chat_failed kind=%s partial=%s',type(exc).__name__,status=='partial')
            yield {'type':'error','message':'回答中断，已保留收到的文字，请重试。','code':'answer_interrupted','partial':status=='partial','request_id':request_id}
        finally:
            if citation_filter is not None: trace['rejected_citations']=citation_filter.rejected
            logging.getLogger(__name__).info('chat_evidence request_id=%s status=%s path=%s evidence=%s',
                request_id,status,trace['path'],{'provenance':trace,'knowledge_revision':generation,
                    'first_valid_text_ms':first_text_ms,'first_content_audio_ready_ms':first_audio_ready_ms,
                    'total_ms':round((time.monotonic()-started)*1000,2)})
            model_trace.reset(trace_token)
            tasks=list(pending.values())
            for task in tasks: task.cancel()
            with anyio.CancelScope(shield=True):
                if tasks: await asyncio.gather(*tasks,return_exceptions=True)
                try:
                    async with async_session() as db:
                        await db.execute(update(ChatMessage).where(ChatMessage.request_id==request_id).values(outcome=status))
                        db.add(ChatMessage(session_id=session_id,role='assistant',content=answer,outcome=status,request_id=request_id))
                        await db.commit()
                    if status in ('completed','refused'):
                        feedback_id=await self._log_feedback(tourist_id,query,answer)
                    persisted=True
                except Exception as exc:
                    logging.getLogger(__name__).warning('chat_persistence_failed kind=%s',type(exc).__name__)
        yield {'type':'done','full_text':answer,'emotion':emotion,'status':status,'request_id':request_id,
               'latency_ms':round((time.monotonic()-started)*1000),'feedback_id':feedback_id,'persisted':persisted,
               'knowledge_revision':generation,'provenance':trace,
               'timings':{'first_valid_text_ms':first_text_ms,'first_content_audio_ready_ms':first_audio_ready_ms,
                          'first_actual_audio_ms':None,'total_ms':round((time.monotonic()-started)*1000,2)},
               'mode':'demo' if settings.DEMO_MODE else trace['path']}


chat_service=ChatService()
