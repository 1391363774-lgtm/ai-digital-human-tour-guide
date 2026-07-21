from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.services.llm_client import ChatMessage
from app.services.rag_service import RagHit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = PROJECT_ROOT / "ai" / "prompts" / "scenic_guide_qa.md"

OFF_TOPIC_PATTERNS = re.compile(
    r"天气预报|明天.*雨|股票|基金|编程|代码|python|java|政治|选举|"
    r"世界杯|nba|英超|欧冠|彩票|汇率|美元|人民币汇率|"
    r"怎么.*赚钱|投资理财|贷款|房贷|"
    r"今天.*几号|现在.*几点|闹钟|"
    r"翻译.*英语|translate|how to|what is",
    re.IGNORECASE,
)

SCENIC_KEYWORDS = re.compile(
    r"灵山|拈花|大佛|梵宫|九龙|灌浴|降魔|五印|坛城|"
    r"五明|佛足|五智|菩提|照壁|阿育王|百子|弥勒|"
    r"祥符|禅寺|曼飞龙|无尽意|微笑广场|妙音台|"
    r"半山衔日|香月花街|禅意小镇|景点|路线|导览|"
    r"游览|门票|开放时间|演出|讲解|知识库|"
    r"景区|导航|地图|收藏|历史记录|反馈|满意度|"
    r"行为|数据大屏|数字人|语音|TTS|ASR|RAG",
)


@dataclass(frozen=True)
class PromptBuildResult:
    messages: list[ChatMessage]
    should_refuse: bool
    refusal_answer: str | None


class ScenicGuidePromptBuilder:
    def __init__(self, min_score: float = 0.0) -> None:
        self.min_score = min_score

    def build(
        self,
        question: str,
        hits: list[RagHit],
        history: list[ChatMessage] | None = None,
    ) -> PromptBuildResult:
        if self._is_off_topic(question):
            return PromptBuildResult(
                messages=[],
                should_refuse=True,
                refusal_answer=(
                    "这个问题超出了我的讲解范围。"
                    "我是灵山胜境的 AI 导游，"
                    "主要为您解答景区景点、文化、路线等方面的问题。"
                    "您可以问我具体的景点介绍、游玩路线或演出时间哦！"
                ),
            )

        reliable_hits = [hit for hit in hits if hit.score >= self.min_score]
        if not reliable_hits:
            return PromptBuildResult(
                messages=[],
                should_refuse=True,
                refusal_answer=(
                    "当前知识库暂未找到可靠依据，我不能编造景区事实。"
                    "你可以换个问法，或先让管理员补充相关景区资料。"
                ),
            )

        context = build_context_from_hits(reliable_hits)
        template = load_prompt_template()
        system_prompt = template.format(context=context, question=question)
        history_messages = history or []
        return PromptBuildResult(
            messages=[
                ChatMessage(role="system", content=system_prompt),
                *history_messages,
                ChatMessage(role="user", content=question),
            ],
            should_refuse=False,
            refusal_answer=None,
        )

    @staticmethod
    def _is_off_topic(question: str) -> bool:
        if OFF_TOPIC_PATTERNS.search(question):
            if not SCENIC_KEYWORDS.search(question):
                return True
        return False


def build_context_from_hits(hits: list[RagHit], max_chars: int = 1600) -> str:
    parts: list[str] = []
    used_chars = 0
    for index, hit in enumerate(hits, start=1):
        title = hit.source.get("section_title") or hit.source.get("document_title") or "知识片段"
        block = f"[资料{index}] {title}\n{hit.content}"
        if used_chars + len(block) > max_chars:
            break
        parts.append(block)
        used_chars += len(block)
    return "\n\n".join(parts)


def load_prompt_template() -> str:
    if PROMPT_PATH.exists():
        return PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "你是灵山胜境 AI 数字人导游。只能基于资料回答，不能编造。\n"
        "知识库资料：\n{context}\n\n游客问题：{question}"
    )