"""
对话API - SSE流式接口(核心) + 非流式接口(兼容)
"""
import json
from typing import Optional

from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.chat_service import chat_service
from app.core.access import visitor_owner

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    tourist_id: str = "guest"
    interest: Optional[str] = None        # 兴趣偏好(个性化推荐)
    time_budget: Optional[str] = None     # 可用时间
    companions: Optional[str] = None      # 同行人群
    dialect: str = "mandarin"


@router.post("/stream")
async def chat_stream(req: ChatRequest, owner: str = Depends(visitor_owner)):
    """SSE流式对话:文本增量 + 情感标签 + 逐句语音与口型时间轴"""

    async def event_gen():
        try:
            async for evt in chat_service.stream_pipeline(
                query=req.message,
                tourist_id=owner,
                interest=req.interest,
                time_budget=req.time_budget,
                companions=req.companions,
            ):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/send")
async def chat_send(req: ChatRequest, owner: str = Depends(visitor_owner)):
    """非流式兼容接口:聚合全部事件后一次性返回"""
    full_text, emotion, sources, intent = "", "calm", [], "general"
    sentences, latency = [], 0
    async for evt in chat_service.stream_pipeline(
        query=req.message, tourist_id=owner,
        interest=req.interest, time_budget=req.time_budget, companions=req.companions,
    ):
        if evt["type"] == "meta":
            sources, intent = evt["sources"], evt["intent"]
        elif evt["type"] == "emotion":
            emotion = evt["emotion"]
        elif evt["type"] == "sentence":
            sentences.append(evt)
        elif evt["type"] == "done":
            full_text, latency = evt["full_text"], evt["latency_ms"]
    return {"answer": full_text, "emotion": emotion, "intent": intent,
            "sources": sources, "sentences": sentences, "latency_ms": latency}


@router.get("/history/{tourist_id}")
async def get_history(tourist_id: str, owner: str = Depends(visitor_owner)):
    if tourist_id != owner:
        raise HTTPException(404,'会话不存在')
    return {"history": await chat_service.get_history(tourist_id, limit=20)}


@router.get('/history')
async def own_history(owner: str = Depends(visitor_owner)):
    return {'history':await chat_service.get_history(owner,limit=20)}


@router.get("/quick-questions")
async def get_quick_questions():
    return {
        "questions": [
            "灵山大佛有多高?",
            "九龙灌浴几点开始表演?",
            "我对佛教历史感兴趣,推荐一条路线",
            "带老人孩子怎么玩比较轻松?",
            "灵山梵宫有什么特别之处?",
            "门票多少钱?怎么预约?",
        ]
    }


class VisionRequest(BaseModel):
    image_b64: str          # base64图片(不含前缀)
    tourist_id: str = "guest"


@router.post("/vision")
async def vision_recognize(req: VisionRequest, owner: str = Depends(visitor_owner)):
    """
    拍照识景(多模态大模型 qwen-vl-max):
    游客拍摄景点照片 → 视觉大模型识别 → 返回数字人讲解文本+语音口型
    """
    from app.services.llm_service import llm_service, strip_emotion, parse_emotion
    from app.services.rag_service import rag_service
    from app.services.tts_service import tts_service

    # 通用景区检索(为视觉识别提供候选资料)
    chunks = await rag_service.retrieve("景点介绍 灵山大佛 梵宫 九龙灌浴", top_k=3)
    answer = await llm_service.vision_identify(req.image_b64, chunks)
    if not answer:
        return {"ok": False, "message": "视觉识别服务暂不可用"}
    emotion = parse_emotion(answer)
    text = strip_emotion(answer)
    tts = tts_service.grant_audio(await tts_service.synthesize(text))
    return {
        "ok": True, "text": text, "emotion": emotion,
        "audio_url": tts.get("audio_url"), "visemes": tts.get("visemes", []),
        "duration_ms": tts.get("duration_ms", 0),
        "model": "qwen-vl-max(多模态)",
    }
