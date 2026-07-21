from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.conversation_repository import ConversationRepository
from app.services.llm_client import ChatMessage, LLMClientError, get_llm_client
from app.services.prompt_service import ScenicGuidePromptBuilder
from app.services.rag_service import RagHit, RagService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatAnswer:
    answer: str
    provider: str
    model: str
    conversation_id: int | None
    sources: list[RagHit]
    refused: bool
    extra: dict[str, Any]


class ChatService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.conversation_repository = ConversationRepository(db)
        self.rag_service = RagService(db)
        self.prompt_builder = ScenicGuidePromptBuilder()

    def prepare_stream(
        self, question: str, top_k: int = 5, conversation_id: int | None = None
    ) -> tuple[object, list[ChatMessage], list[RagHit], str | None]:
        """准备流式回答：创建会话、检索、构建 prompt。返回 (conversation, messages, hits, refusal_text)。
        如果 refusal_text 不为 None，说明应该拒答。
        """
        conversation = self.conversation_repository.get_or_create(conversation_id, title=question)
        history_messages = [
            ChatMessage(role=message.role, content=message.content)
            for message in self.conversation_repository.list_recent_messages(conversation.id, limit=6)
            if message.role in {"user", "assistant"}
        ]
        self.conversation_repository.add_message(conversation, role="user", content=question)

        hits = self.rag_service.search(question, top_k=min(top_k, 4))
        prompt = self.prompt_builder.build(question, hits, history=history_messages)

        refusal = prompt.refusal_answer if prompt.should_refuse else None
        return conversation, prompt.messages if not prompt.should_refuse else [], hits, refusal

    def persist_stream_answer(
        self, conversation, answer: str, sources: list[RagHit], started_at: float
    ) -> None:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        srcs = [
            {"content": hit.content[:500], "score": hit.score, "metadata": hit.source}
            for hit in sources
        ]
        self.conversation_repository.add_message(
            conversation, role="assistant", content=answer, sources=srcs, latency_ms=latency_ms
        )

    def answer(self, question: str, top_k: int = 5, conversation_id: int | None = None, fast: bool = False) -> ChatAnswer:
        started_at = time.perf_counter()
        timing: dict[str, int] = {}

        stage_at = time.perf_counter()
        conversation = self.conversation_repository.get_or_create(conversation_id, title=question)
        history_messages = [
            ChatMessage(role=message.role, content=message.content)
            for message in self.conversation_repository.list_recent_messages(conversation.id, limit=6)
            if message.role in {"user", "assistant"}
        ]
        self.conversation_repository.add_message(conversation, role="user", content=question)
        timing["history_ms"] = elapsed_ms(stage_at)

        if fast:
            direct_answer = build_direct_fast_answer(question)
            if direct_answer:
                answer = ChatAnswer(
                    answer=direct_answer,
                    provider="local_fast_memory",
                    model="scenic-memory-v1",
                    conversation_id=conversation.id,
                    sources=[],
                    refused=False,
                    extra={"timing": timing, "fast": True},
                )
                self._persist_assistant_answer(conversation, answer, started_at)
                self._log_timing(question, timing, started_at, provider="local_fast_memory")
                return answer

        stage_at = time.perf_counter()
        hits = self.rag_service.fast_search(question, top_k=min(top_k, 3)) if fast else self.rag_service.search(question, top_k=min(top_k, 4))
        timing["rag_ms"] = elapsed_ms(stage_at)

        stage_at = time.perf_counter()
        prompt = self.prompt_builder.build(question, hits, history=history_messages)
        timing["prompt_ms"] = elapsed_ms(stage_at)
        if prompt.should_refuse:
            answer = ChatAnswer(
                answer=prompt.refusal_answer or "当前知识库暂未找到可靠依据。",
                provider="rule",
                model="refusal",
                conversation_id=conversation.id,
                sources=hits,
                refused=True,
                extra={"timing": timing},
            )
            self._persist_assistant_answer(conversation, answer, started_at)
            self._log_timing(question, timing, started_at, provider="rule")
            return answer

        if fast:
            answer = ChatAnswer(
                answer=build_fast_rag_answer(question, hits),
                provider="local_fast_rag",
                model="extractive-guide-v1",
                conversation_id=conversation.id,
                sources=hits,
                refused=False,
                extra={"timing": timing, "fast": True},
            )
            self._persist_assistant_answer(conversation, answer, started_at)
            self._log_timing(question, timing, started_at, provider="local_fast_rag")
            return answer

        llm_client = get_llm_client()
        try:
            stage_at = time.perf_counter()
            response = llm_client.chat(prompt.messages)
            timing["llm_ms"] = elapsed_ms(stage_at)
            answer = ChatAnswer(
                answer=response.content,
                provider=response.provider,
                model=response.model,
                conversation_id=conversation.id,
                sources=hits,
                refused=False,
                extra={"timing": timing},
            )
            self._persist_assistant_answer(conversation, answer, started_at)
            self._log_timing(question, timing, started_at, provider=response.provider)
            return answer
        except LLMClientError as exc:
            timing["llm_error_ms"] = elapsed_ms(stage_at)
            fallback = (
                "AI 模型暂时不可用，但我已找到相关知识资料。"
                "请先参考下方来源内容，或稍后重试。"
            )
            answer = ChatAnswer(
                answer=fallback,
                provider="fallback",
                model="llm_error",
                conversation_id=conversation.id,
                sources=hits,
                refused=False,
                extra={"error": str(exc), "timing": timing},
            )
            self._persist_assistant_answer(conversation, answer, started_at)
            self._log_timing(question, timing, started_at, provider="fallback")
            return answer

    def _persist_assistant_answer(self, conversation, answer: ChatAnswer, started_at: float) -> None:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        sources = [
            {
                "content": hit.content[:500],
                "score": hit.score,
                "metadata": hit.source,
            }
            for hit in answer.sources
        ]
        self.conversation_repository.add_message(
            conversation,
            role="assistant",
            content=answer.answer,
            sources=sources,
            latency_ms=latency_ms,
        )

    def _log_timing(self, question: str, timing: dict[str, int], started_at: float, provider: str) -> None:
        logger.info(
            "chat_timing provider=%s total_ms=%s history_ms=%s rag_ms=%s prompt_ms=%s llm_ms=%s question=%s",
            provider,
            elapsed_ms(started_at),
            timing.get("history_ms", 0),
            timing.get("rag_ms", 0),
            timing.get("prompt_ms", 0),
            timing.get("llm_ms", timing.get("llm_error_ms", 0)),
            question[:80],
        )


def elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


FAST_SPOT_SUMMARIES = {
    "灵山大佛": "灵山大佛通高88米，是灵山胜境核心地标，重点体现佛教文化和太湖山水视野。",
    "九龙灌浴": "九龙灌浴是代表性演艺体验，适合观看动态表演，感受佛教故事与音乐喷泉结合。",
    "灵山梵宫": "灵山梵宫以佛教艺术空间著称，适合欣赏建筑、壁画和文化展陈。",
    "五印坛城": "五印坛城体现藏传佛教坛城文化，适合讲解五方五佛和宗教艺术。",
    "祥符禅寺": "祥符禅寺延续灵山佛教文脉，适合安静参访并了解寺院历史。",
    "拈花湾禅意小镇": "拈花湾禅意小镇主打休闲体验，适合慢游、夜景、演艺和禅意街区体验。",
    "拈花湾": "拈花湾偏休闲度假和禅意小镇体验，适合夜游、慢行和拍照。",
    "微笑广场": "微笑广场是拈花湾重要打卡点，适合拍照和体验轻松开放的禅意空间。",
    "妙音台": "妙音台偏演艺体验，适合结合音乐、灯光和夜游节奏安排。",
    "大照壁": "灵山大照壁是入口代表景观，适合拍照，并引入赵朴初题字和佛教文化背景。",
    "降魔成道": "降魔成道适合按演艺体验讲解，用故事化方式介绍佛陀成道前的考验。",
}


def build_direct_fast_answer(question: str) -> str | None:
    normalized = question.strip()
    for name, summary in FAST_SPOT_SUMMARIES.items():
        if name in normalized:
            return f"{summary}\n\n我可以继续讲路线。"
    if "历史" in normalized and ("感兴趣" in normalized or "路线" in normalized):
        return "喜欢历史文化，建议优先走大照壁、九龙灌浴、祥符禅寺、灵山大佛这条中轴线。\n\n我可以继续讲路线。"
    if "自然" in normalized or "风光" in normalized:
        return "喜欢自然风光，建议结合太湖视野、灵山大佛高处视野和拈花湾慢行街区游览。\n\n我可以继续讲路线。"
    return None


def build_fast_rag_answer(question: str, hits: list[RagHit]) -> str:
    if not hits:
        return "当前知识库暂未找到可靠依据，我不能编造景区事实。你可以换个景点或换一种问法。"

    question_terms = [
        term for term in
        ("灵山大佛", "九龙灌浴", "灵山梵宫", "五印坛城", "拈花湾", "大照壁",
         "祥符禅寺", "阿育王柱", "百子戏弥勒", "降魔", "佛足坛", "菩提大道",
         "五智门", "五明桥", "曼飞龙塔", "无尽意斋", "佛教文化博览馆")
        if term in question
    ]
    picked: list[str] = []
    for hit in hits[:5]:
        content = " ".join(hit.content.replace("\r", "\n").split())
        sentences = split_sentences(content)
        # 优先挑选包含问题关键词的句子
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or sentence in picked:
                continue
            if any(term in sentence for term in question_terms):
                picked.append(sentence)
                if len(picked) >= 5:
                    break
        if len(picked) >= 5:
            break

    # 如果关键词没匹配到，用前几条内容
    if not picked:
        for hit in hits[:3]:
            content = " ".join(hit.content.replace("\r", "\n").split())
            first = content[:300].strip()
            if first and first not in picked:
                picked.append(first)
            if len(picked) >= 3:
                break

    if not picked:
        picked = [" ".join(hits[0].content.split())[:300]]

    answer = "。".join(picked) + "。"
    if len(answer) > 62:
        answer = answer[:58].rstrip("，。；、 ") + "。"
    return f"{answer}\n\n我可以继续讲路线。"


def split_sentences(text: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for char in text:
        current += char
        if char in "。！？；\n":
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    return [chunk for chunk in chunks if chunk]
