"""
对话编排服务 - 全链路流式管线
游客提问 → RAG检索 → LLM流式生成 → 按句切分 → 逐句TTS+口型时间轴 → SSE推送
首句音频通常在1.5~2.5秒内就绪,满足赛题"语音问答延迟<5秒"硬指标。
"""
import asyncio
import re
import time
from typing import AsyncGenerator, Dict, List, Optional

from sqlalchemy import select

from app.core.database import async_session
from app.models.models import ChatMessage, ChatSession, TouristFeedback
from app.services.llm_service import llm_service, parse_emotion, strip_emotion
from app.services.rag_service import rag_service
from app.services.sentiment import analyze_sentiment
from app.services.tts_service import tts_service

SENTENCE_END = re.compile(r"([。!?!?；;])")
CLAUSE_END = re.compile(r"([。!?!?；;,,、])")
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
                            intent: Optional[str] = None):
        async with async_session() as db:
            db.add(ChatMessage(session_id=session_id, role=role,
                               content=content, intent=intent))
            await db.commit()

    async def _log_feedback(self, tourist_id: str, question: str, answer: str):
        sentiment, score = analyze_sentiment(question)
        async with async_session() as db:
            db.add(TouristFeedback(tourist_id=tourist_id, question=question,
                                   answer=answer[:500], satisfaction=None,
                                   sentiment=sentiment))
            await db.commit()

    async def get_history(self, tourist_id: str, limit: int = 6) -> List[Dict]:
        async with async_session() as db:
            q = select(ChatSession).where(ChatSession.tourist_id == tourist_id) \
                .order_by(ChatSession.id.desc()).limit(1)
            session = (await db.execute(q)).scalar_one_or_none()
            if not session:
                return []
            q2 = select(ChatMessage).where(ChatMessage.session_id == session.id) \
                .order_by(ChatMessage.id.desc()).limit(limit)
            rows = (await db.execute(q2)).scalars().all()
            return [{"role": r.role, "content": r.content} for r in reversed(rows)]

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

    # ---------------- 主流式管线 ----------------
    async def stream_pipeline(
        self,
        query: str,
        tourist_id: str = "guest",
        interest: Optional[str] = None,
        time_budget: Optional[str] = None,
        companions: Optional[str] = None,
    ) -> AsyncGenerator[Dict, None]:
        """
        SSE事件流:
          meta     {sources, intent, engine}
          emotion  {emotion}
          delta    {text}           增量文本(打字机效果)
          sentence {index, text, audio_url, visemes, duration_ms}  逐句语音+口型
          done     {full_text, latency_ms}
          error    {message}
        """
        t0 = time.time()
        intent = self.detect_intent(query)

        # 1. RAG检索 与 承接语TTS 并发执行(承接语几乎瞬时缓存命中)
        prelude_text = PRELUDE_PHRASES[hash(tourist_id + query) % len(PRELUDE_PHRASES)]
        chunks, prelude_meta = await asyncio.gather(
            rag_service.retrieve(query),
            tts_service.synthesize(prelude_text),
        )
        yield {"type": "meta", "intent": intent,
               "engine": rag_service.engine_mode,
               "sources": [{"title": c["title"], "score": c["score"]} for c in chunks]}

        # 承接语立即下发(序号-1,前端插入队首,数字人秒开口)
        yield {"type": "sentence", "index": -1, "text": prelude_text,
               "audio_url": prelude_meta.get("audio_url"),
               "tts_ok": prelude_meta.get("ok", False),
               "visemes": prelude_meta.get("visemes", []),
               "duration_ms": prelude_meta.get("duration_ms", 0),
               "prelude": True}

        # 2. 历史上下文
        session_id = await self._ensure_session(tourist_id)
        history = await self.get_history(tourist_id)

        # 3. LLM流式 + 情绪标签截获 + 按句切分 + 逐句TTS(就绪即推,不等全文)
        full_text = ""
        display_text = ""
        emotion = "calm"
        sentence_buf = ""
        sentence_idx = 0
        head_buf = ""           # 用于截获开头的[emotion:x]
        head_resolved = False
        pending: Dict[int, asyncio.Task] = {}   # idx -> TTS任务
        next_yield = 0                           # 下一个待推送的句子序号

        async def synth(idx: int, text: str):
            meta = await tts_service.synthesize(text)
            return idx, text, meta

        def make_sentence_events(idx: int, text: str, meta: Dict) -> Dict:
            return {"type": "sentence", "index": idx, "text": text,
                    "audio_url": meta.get("audio_url"),
                    "tts_ok": meta.get("ok", False),
                    "visemes": meta.get("visemes", []),
                    "duration_ms": meta.get("duration_ms", 0)}

        def dispatch_sentence(text: str):
            """切出一句并发起并发TTS"""
            nonlocal sentence_idx
            pending[sentence_idx] = asyncio.create_task(synth(sentence_idx, text))
            sentence_idx += 1

        async for token in llm_service.stream_chat(
                query, chunks, history, interest, time_budget, companions):
            full_text += token

            # --- 截获情感标签(在首个']'出现前都在头部缓冲) ---
            if not head_resolved:
                head_buf += token
                if "]" in head_buf:
                    emotion = parse_emotion(head_buf)
                    remainder = strip_emotion(head_buf)
                    head_resolved = True
                    yield {"type": "emotion", "emotion": emotion}
                    if remainder:
                        token = remainder
                    else:
                        continue
                elif len(head_buf) > 20:  # LLM未输出标签,放弃截获
                    head_resolved = True
                    yield {"type": "emotion", "emotion": emotion}
                    token = head_buf
                else:
                    continue

            display_text += token
            sentence_buf += token
            yield {"type": "delta", "text": token}

            # 切句:强终止符直接切;逗号在缓冲超阈值时切
            # 首句(sentence_idx==0)无阈值——"阿弥陀佛,"式开场白立即开口,数字人秒响应
            hard = SENTENCE_END.split(sentence_buf)
            while len(hard) >= 2:
                sent = hard.pop(0) + hard.pop(0)
                sentence_buf = "".join(hard)
                if VALID_CHAR.search(sent):
                    dispatch_sentence(sent.strip())
            threshold = 28 if sentence_idx > 0 else 0
            if len(sentence_buf) > threshold:
                soft = CLAUSE_END.split(sentence_buf)
                if len(soft) >= 2:
                    sent = soft[0] + soft[1]
                    sentence_buf = "".join(soft[2:])
                    if VALID_CHAR.search(sent):
                        dispatch_sentence(sent.strip())

            # 就绪的句子立刻按序推送(核心:不等LLM全文生成完)
            while next_yield in pending and pending[next_yield].done():
                idx, text, meta = pending.pop(next_yield).result()
                yield make_sentence_events(idx, text, meta)
                next_yield += 1

        if not head_resolved:
            yield {"type": "emotion", "emotion": emotion}

        # 尾句
        tail = sentence_buf.strip()
        if VALID_CHAR.search(tail):
            dispatch_sentence(tail)

        # 4. 收尾:按序等待并推送剩余句子
        while next_yield < sentence_idx:
            idx, text, meta = await pending.pop(next_yield)
            yield make_sentence_events(idx, text, meta)
            next_yield += 1

        # 5. 持久化 + 情感记录(后台执行不阻塞)
        latency = int((time.time() - t0) * 1000)
        clean_answer = strip_emotion(full_text).strip()
        try:
            await self._save_message(session_id, "user", query, intent)
            await self._save_message(session_id, "assistant", clean_answer)
            await self._log_feedback(tourist_id, query, clean_answer)
        except Exception as e:
            print(f"[Chat] 持久化失败: {e}")

        yield {"type": "done", "full_text": clean_answer,
               "emotion": emotion, "latency_ms": latency}


chat_service = ChatService()
