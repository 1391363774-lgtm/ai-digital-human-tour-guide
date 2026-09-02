from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.behavior import router as behavior_router
from app.api.routes.avatar_config import router as avatar_config_router
from app.api.routes.chat import router as chat_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.favorite import router as favorite_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.history import router as history_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.multimodal import router as multimodal_router
from app.api.routes.rag import router as rag_router
from app.api.routes.route import router as route_router
from app.api.routes.scenic import router as scenic_router
from app.api.routes.speech import router as speech_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.response import success
from app.services.speech_service import prewarm_tts_cache

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _prewarm_tts():
    """后台预合成热点景点介绍音频，预热后 TTS 延迟从 ~8s 降至 <50ms。"""
    import asyncio
    import logging

    from app.services.chat_service import FAST_SPOT_SUMMARIES

    logger = logging.getLogger("app.tts.prewarm")
    texts = list(FAST_SPOT_SUMMARIES.values())

    # 扩展预热：常见问答的固定回复文本
    extra_texts = [
        # 景点推荐
        "灵山胜境有许多值得游览的景点，我为您推荐几大核心景点：\n"
        "1. 灵山大佛 — 通高88米的青铜巨佛，是景区核心地标。\n"
        "2. 九龙灌浴 — 再现释迦牟尼诞生场景的动态演艺景观。\n"
        "3. 灵山梵宫 — 占地3万平方米的佛教艺术殿堂，内有《灵山吉祥颂》演出。\n"
        "4. 五印坛城 — 藏传佛教风格建筑，展示藏传佛教艺术珍品。\n"
        "5. 拈花湾禅意小镇 — 唐风禅意主题度假小镇，适合慢游和夜游。\n\n"
        "您想了解哪个景点的详细信息？可以直接问我哦！",
        # 历史路线
        "喜欢历史文化，建议优先游览大照壁、佛足坛、菩提大道、九龙灌浴、祥符禅寺、灵山大佛这条中轴线。"
        "这条路线涵盖了玄奘命名'小灵山'的历史渊源、释迦牟尼诞生的动态演绎、以及千年古刹祥符禅寺的文化积淀，"
        "是感受灵山佛教文化历史脉络的经典线路。",
        # 自然路线
        "喜欢自然风光，建议结合太湖视野、灵山大佛高处观景台和拈花湾慢行街区游览。"
        "灵山胜境依山傍水，处于秦履峰、青龙山、白虎山之间，四季分明、日照充足；"
        "拈花湾的半山衔日更是观赏自然风光的绝佳位置。",
        # 门票信息
        "灵山胜境的门票信息建议您关注景区官方渠道获取最新价格。"
        "一般成人票包含灵山大佛、九龙灌浴、灵山梵宫等核心景点。"
        "拈花湾禅意小镇通常可免费进入街区游览，部分演艺项目可能需另购票。",
        # 开放时间
        "灵山胜境景区一般为每日7:30-17:30开放（季节可能略有调整，建议出行前查看官方公告）。"
        "九龙灌浴演艺通常在日间固定时段演出，灵山梵宫《灵山吉祥颂》也有固定场次。",
        # 默认问候
        "你好，我是灵山胜境 AI 数字人导游。我可以讲景点故事、推荐路线，也可以用语音为你讲解。",
        # 拒答文本1：超出讲解范围（天气/笑话等）
        "这个问题超出了我的讲解范围。"
        "我是灵山胜境的 AI 导游，"
        "主要为您解答景区景点、文化、路线等方面的问题。"
        "您可以问我：灵山大佛有多高？九龙灌浴什么时候表演？"
        "灵山梵宫里有什么？或者让我推荐一条游览路线！",
        # 拒答文本2：未找到可靠资料
        "这个问题我暂时没有找到准确的资料，不能随意编造。"
        "我是灵山胜境 AI 导游，可以为您介绍灵山大佛、九龙灌浴、"
        "灵山梵宫、五印坛城、拈花湾等景点，也可以推荐游览路线哦！"
        "欢迎换一个景点来问我。",
    ]
    texts.extend(extra_texts)

    # 后台执行，不阻塞启动
    asyncio.create_task(_do_prewarm(texts, logger))


async def _do_prewarm(texts: list[str], logger):
    import asyncio
    import time

    await asyncio.sleep(2)  # 等待启动完成
    t0 = time.perf_counter()
    logger.info("开始并行预合成热点景点音频（%d 条文本）...", len(texts))
    count = await prewarm_tts_cache(texts)
    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.info("预合成完成：%d 段音频已缓存，耗时 %dms", count, elapsed)


@app.get("/health")
def health_check():
    return success({"status": "ok", "env": settings.app_env})


app.include_router(knowledge_router)
app.include_router(multimodal_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(route_router)
app.include_router(speech_router)
app.include_router(scenic_router)
app.include_router(favorite_router)
app.include_router(feedback_router)
app.include_router(behavior_router)
app.include_router(dashboard_router)
app.include_router(avatar_config_router)
