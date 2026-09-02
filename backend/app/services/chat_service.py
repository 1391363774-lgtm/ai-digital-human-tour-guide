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

    def _enrich_with_spot_summaries(self, question: str, hits: list[RagHit]) -> list[RagHit]:
        """将匹配的景点摘要注入检索结果，确保关键事实数据进入 LLM 上下文。"""
        existing_content = {h.content[:60] for h in hits}
        enriched = list(hits)
        for name, summary in FAST_SPOT_SUMMARIES.items():
            if name in question and summary[:60] not in existing_content:
                enriched.insert(0, RagHit(
                    content=summary,
                    score=1.0,
                    source={"section_title": f"景点档案：{name}", "document_title": "景区核心数据", "retrieval": "spot_summary"},
                ))
        return enriched

    def prepare_stream(
        self, question: str, top_k: int = 5, conversation_id: int | None = None, fast: bool = False
    ) -> tuple[object, list[ChatMessage], list[RagHit], str | None, str | None]:
        """准备流式回答：创建会话、检索、构建 prompt。
        返回 (conversation, messages, hits, refusal_text, fast_answer)。
        如果 refusal_text 不为 None，说明应该拒答。
        """
        conversation = self.conversation_repository.get_or_create(conversation_id, title=question)
        history_messages = [
            ChatMessage(role=message.role, content=message.content)
            for message in self.conversation_repository.list_recent_messages(conversation.id, limit=6)
            if message.role in {"user", "assistant"}
        ]
        self.conversation_repository.add_message(conversation, role="user", content=question)

        dynamic_refusal = build_dynamic_info_refusal(question)
        if dynamic_refusal:
            return conversation, [], [], dynamic_refusal, None

        if fast:
            direct_answer = build_direct_fast_answer(question)
            if direct_answer:
                return conversation, [], [], None, direct_answer

        hits = self.rag_service.fast_search(question, top_k=max(top_k, 6)) if fast else self.rag_service.search(question, top_k=min(top_k, 6))
        if not fast:
            hits = self._enrich_with_spot_summaries(question, hits)
        prompt = self.prompt_builder.build(question, hits, history=history_messages)

        refusal = prompt.refusal_answer if prompt.should_refuse else None

        if fast and not prompt.should_refuse:
            fast_answer = build_fast_rag_answer(question, hits)
            return conversation, [], hits, None, fast_answer

        return conversation, prompt.messages if not prompt.should_refuse else [], hits, refusal, None

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

        dynamic_refusal = build_dynamic_info_refusal(question)
        if dynamic_refusal:
            answer = ChatAnswer(
                answer=dynamic_refusal,
                provider="rule",
                model="dynamic-info-boundary",
                conversation_id=conversation.id,
                sources=[],
                refused=True,
                extra={"timing": timing},
            )
            self._persist_assistant_answer(conversation, answer, started_at)
            self._log_timing(question, timing, started_at, provider="rule")
            return answer

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
        hits = self.rag_service.fast_search(question, top_k=max(top_k, 6)) if fast else self.rag_service.search(question, top_k=min(top_k, 6))
        if not fast:
            hits = self._enrich_with_spot_summaries(question, hits)
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


def build_dynamic_info_refusal(question: str) -> str | None:
    """对知识库没有可靠实时来源的信息明确拒答，避免给出过时推荐。"""
    normalized = question.strip()
    if any(word in normalized for word in ("门票", "票价", "怎么买票", "购票")):
        return (
            "门票价格和购票规则可能随日期、活动与人群政策变化，"
            "当前知识库没有可核验的实时票务数据，我不能给出未经确认的价格。"
            "请以灵山胜境官方渠道或现场售票信息为准。"
        )
    if any(word in normalized for word in ("餐厅", "饭店", "好吃", "酒店", "住宿", "住哪里")):
        return (
            "当前知识库没有经过核验的实时餐饮或住宿名录，我不能直接推荐具体商家。"
            "建议查看景区官方服务信息或正规地图平台的最新营业状态与评价。"
        )
    return None


FAST_SPOT_SUMMARIES = {
    "灵山大佛": (
        "灵山大佛是灵山胜境的核心地标，于1997年建成开光。"
        "大佛通高88米，其中佛体高79米、莲花座高9米，加上三层台基总高度达101.5米，"
        "由青铜铸造，耗铜725吨，是中国最高的巨型佛像之一。"
        "大佛为释迦牟尼佛旃檀佛像立姿，位于祥符禅寺后方，因所在位置即唐玄奘命名的'小灵山'而得名。"
        "灵山大佛与四川乐山大佛、香港天坛大佛、山西云冈大佛、河南龙门大佛共同形成中华大地'五方五佛'的格局。"
    ),
    "九龙灌浴": (
        "九龙灌浴是灵山胜境最具代表性的动态演艺景观，位于景区中心地带。"
        "景观根据佛教故事中释迦牟尼诞生时的情景而建造，雕塑总高27.2米，使用黄金18千克，耗铜180吨。"
        "高7.2米的太子佛塑像立于巨型莲池之中，四大力士托起莲花，莲花每瓣长达6米。"
        "莲花周围绕以九条龙喷水，另有六位仙女供养太子佛，最外围还有九组共72只凤凰。"
        "随着佛乐奏响，莲花花瓣逐渐开放，通体鎏金的太子佛从花瓣中升起，在九龙喷水形成的水幕中自转一周，"
        "是现代科技与佛教文化的完美结合。"
    ),
    "灵山梵宫": (
        "灵山梵宫是灵山胜境的标志性建筑之一，位于景区东北部，占地30000平方米，于2009年1月1日正式开放。"
        "梵宫外观以菩提伽耶塔风格为主，糅合了中国佛教石窟艺术及传统佛教建筑元素，"
        "顶部五座巨大的莲花圣塔代表'五方五佛'。"
        "内部采用对称退台式布局，廊厅两侧有十二幅名为'世界佛教传法图'的巨幅油画，每幅高达12米。"
        "圣坛面积达3500平方米，穹顶高30米，可容纳2000人，是举办《灵山吉祥颂》大型演出的场所。"
        "梵宫廊厅也是灵山博物馆的主馆区，陈列有琉璃巨制《华藏世界》、飞天木雕、地涌宝塔等艺术珍品。"
    ),
    "五印坛城": (
        "五印坛城位于景区东南部，矗立于香水海之中的圆岛之上，于2011年9月建成。"
        "建筑为五层重檐楼宇，白墙红边金顶，占地面积5000平方米，是灵山博物馆的展馆之一。"
        "'五印坛城'梵文读音'曼陀罗'，汉译为'坛城'或'道场'，内供奉五方五佛因此得名。"
        "山门高8米、宽40米，是按拉萨布达拉宫底下雪村大门仿建。"
        "四门安置守护瑞兽：南门马宝、西门孔雀、北门共命鸟、东门象宝，分别对应五方佛的坐骑。"
        "内部设有藏传佛教艺术珍品馆，展出度母、五大金刚等藏传佛教艺术珍品。"
    ),
    "祥符禅寺": (
        "祥符禅寺位于景区北部，是一座历史悠久的佛教寺院，其前身可追溯至唐代。"
        "相传玄奘法师自天竺取经归来后到此，见秦履峰南麓状似灵鹫山，便称为'小灵山'，"
        "其弟子窥基在此开坛说法，这座小灵山寺即为祥符禅寺前身。"
        "北宋大中祥符年间宋真宗赐名'祥符禅院'，宋徽宗时升院为寺。"
        "现寺内有祥符三桥、弥勒殿、天王殿、大雄宝殿、钟楼、鼓楼等建筑。"
        "大雄宝殿为重檐歇山式建筑，檐下悬有赵朴初先生题写的'祥符禅寺'匾额。"
        "钟楼内悬有高3.8米、口径2.5米、重12.8吨的大钟。"
    ),
    "拈花湾禅意小镇": (
        "拈花湾禅意小镇位于无锡市滨湖区，是一座以唐代禅意文化为主题的休闲度假小镇，总占地面积约1600亩。"
        "小镇以'禅'为核心，融合了唐风建筑、禅意生活和自然山水，"
        "内部汇聚了半山衔日、香月花街、拈花塔、妙音台、微笑广场等多个景观节点。"
        "这里适合慢游、夜游和禅意体验，白天可漫步花街感受唐风古韵，夜晚可欣赏灯光演艺和水幕秀。"
        "拈花湾与灵山胜境景区毗邻，形成'白天看大佛、夜晚游拈花湾'的经典游览组合。"
    ),
    "拈花湾": (
        "拈花湾位于无锡市滨湖区灵山胜境旁，是一座以唐代禅意文化为主题的休闲度假小镇，占地约1600亩。"
        "小镇融合唐风建筑与禅意生活，拥有半山衔日、香月花街、拈花塔、妙音台、微笑广场等景观。"
        "适合慢游、夜游、禅意体验和拍照打卡，是灵山胜境游览的重要补充。"
    ),
    "微笑广场": (
        "微笑广场是拈花湾禅意小镇的重要打卡节点，以开放式的禅意空间设计为特色。"
        "广场以'微笑'为主题，寓意禅宗'拈花微笑'的典故，适合拍照和体验轻松的氛围。"
        "夜晚灯光亮起时，广场成为夜游拈花湾的核心区域之一。"
    ),
    "妙音台": (
        "妙音台是拈花湾禅意小镇的演艺体验节点，以音乐和灯光表演为主要特色。"
        "结合夜间游览节奏，这里会呈现融合音乐、灯光和禅意文化的演艺节目，是体验拈花湾夜游氛围的好去处。"
    ),
    "大照壁": (
        "灵山大照壁是灵山胜境入口处的代表景观，位于景区中轴线起点。"
        "照壁上刻有赵朴初先生的题字，是引入景区佛教文化背景的第一站。"
        "游客经过照壁后依次前往佛足坛、菩提大道、九龙灌浴等核心景点，适合拍照留念。"
    ),
    "降魔成道": (
        "降魔成道是灵山胜境的演艺体验景观之一，以故事化方式呈现佛陀释迦牟尼成道前所经历的考验。"
        "该景观再现了佛陀在菩提树下降伏心魔、最终觉悟成道的故事，"
        "与九龙灌浴、灵山梵宫《灵山吉祥颂》共同构成佛祖成道的文化轴线。"
    ),
    "曼飞龙塔": (
        "曼飞龙塔位于灵山梵宫南侧、五印坛城附近，是一座南传上座部佛教风格的塔群。"
        "塔群造型独特，仿自云南曼飞龙塔，展现了傣族佛教文化和东南亚佛教建筑特色。"
        "塔身洁白，塔尖金色，与周围的藏传佛教五印坛城形成不同佛教文化流派的对比展示。"
    ),
    "灵山博物馆": (
        "灵山博物馆成立于2022年，前身为1997年推出的文博中心和2010年成立的灵山佛教艺术博览馆。"
        "博物馆以梵宫廊厅为主馆区，集纳珍宝馆、五印坛城、无尽意斋、佛教文化博览馆等展览空间。"
        "精品藏品包括东阳木雕、巨幅油画、汉白玉雕刻、琉璃艺术品等，是深入了解灵山佛教文化底蕴的核心场所。"
    ),
    "杏坛广场": (
        "杏坛广场位于祥符禅寺附近，以儒家文化与佛教文化交融为主题。"
        "广场上有古银杏树和六角井、八角井等近千年历史的古迹，是感受中华传统文化与佛教互动的独特空间。"
    ),
    "万年宝鼎": (
        "万年宝鼎是灵山胜境的重要祈福景观，铸造精美，体现了青铜器文化与传统祈福文化的结合。"
        "宝鼎位于景区中轴线附近，是游客祈福许愿的代表性场所。"
    ),
}


def build_direct_fast_answer(question: str) -> str | None:
    normalized = question.strip()
    for name, summary in FAST_SPOT_SUMMARIES.items():
        if name in normalized:
            return summary
    if "历史" in normalized and ("感兴趣" in normalized or "路线" in normalized):
        return (
            "喜欢历史文化，建议优先游览大照壁、佛足坛、菩提大道、九龙灌浴、祥符禅寺、灵山大佛这条中轴线。"
            "这条路线涵盖了玄奘命名'小灵山'的历史渊源、释迦牟尼诞生的动态演绎、以及千年古刹祥符禅寺的文化积淀，"
            "是感受灵山佛教文化历史脉络的经典线路。\n\n我可以继续为您讲路线。"
        )
    if "自然" in normalized or "风光" in normalized:
        return (
            "喜欢自然风光，建议结合太湖视野、灵山大佛高处观景台和拈花湾慢行街区游览。"
            "灵山胜境依山傍水，处于秦履峰、青龙山、白虎山之间，四季分明、日照充足；"
            "拈花湾的半山衔日更是观赏自然风光的绝佳位置。\n\n我可以继续为您讲路线。"
        )
    # 常见泛化问题：推荐、好玩、必去、攻略、介绍景区
    if any(kw in normalized for kw in ("推荐", "好玩", "必去", "攻略", "介绍", "有什么", "景点有哪些")):
        return (
            "灵山胜境有许多值得游览的景点，我为您推荐几大核心景点：\n"
            "1. 灵山大佛 — 通高88米的青铜巨佛，是景区核心地标。\n"
            "2. 九龙灌浴 — 再现释迦牟尼诞生场景的动态演艺景观。\n"
            "3. 灵山梵宫 — 占地3万平方米的佛教艺术殿堂，内有《灵山吉祥颂》演出。\n"
            "4. 五印坛城 — 藏传佛教风格建筑，展示藏传佛教艺术珍品。\n"
            "5. 拈花湾禅意小镇 — 唐风禅意主题度假小镇，适合慢游和夜游。\n\n"
            "您想了解哪个景点的详细信息？可以直接问我哦！"
        )
    if "门票" in normalized or "票价" in normalized or "多少钱" in normalized:
        return (
            "灵山胜境的门票信息建议您关注景区官方渠道获取最新价格。"
            "一般成人票包含灵山大佛、九龙灌浴、灵山梵宫等核心景点。"
            "拈花湾禅意小镇通常可免费进入街区游览，部分演艺项目可能需另购票。"
            "\n\n您还想了解哪些景点的信息？"
        )
    if "开放时间" in normalized or "几点" in normalized and "开放" in normalized:
        return (
            "灵山胜境景区一般为每日7:30-17:30开放（季节可能略有调整，建议出行前查看官方公告）。"
            "九龙灌浴演艺通常在日间固定时段演出，灵山梵宫《灵山吉祥颂》也有固定场次。"
            "\n\n您还想了解哪些景点的信息？"
        )
    return None


def build_fast_rag_answer(question: str, hits: list[RagHit]) -> str:
    if not hits:
        return "当前知识库暂未找到可靠依据，我不能编造景区事实。你可以换个景点或换一种问法。"

    question_terms = [
        term for term in
        ("灵山大佛", "九龙灌浴", "灵山梵宫", "五印坛城", "拈花湾", "大照壁",
         "祥符禅寺", "阿育王柱", "百子戏弥勒", "降魔", "佛足坛", "菩提大道",
         "五智门", "五明桥", "曼飞龙塔", "无尽意斋", "佛教文化博览馆",
         "拈花塔", "香月花街", "微笑广场", "妙音台", "半山衔日", "杏坛广场")
        if term in question
    ]
    picked: list[str] = []
    for hit in hits[:6]:
        content = " ".join(hit.content.replace("\r", "\n").split())
        sentences = split_sentences(content)
        # 优先挑选包含问题关键词的句子
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or sentence in picked:
                continue
            if any(term in sentence for term in question_terms):
                picked.append(sentence)
                if len(picked) >= 8:
                    break
        if len(picked) >= 8:
            break

    # 如果关键词没匹配到，用前几条内容的前几句
    if not picked:
        for hit in hits[:4]:
            content = " ".join(hit.content.replace("\r", "\n").split())
            sentences = split_sentences(content)
            for sentence in sentences[:3]:
                sentence = sentence.strip()
                if sentence and sentence not in picked:
                    picked.append(sentence)
                if len(picked) >= 6:
                    break
            if len(picked) >= 6:
                break

    if not picked:
        picked = [" ".join(hits[0].content.split())[:400]]

    answer = "。".join(picked) + "。"
    return answer


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
