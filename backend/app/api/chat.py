"""
对话API - SSE流式接口(核心) + 非流式接口(兼容)
"""
import json
import asyncio
import time
import uuid
from contextlib import aclosing
from typing import Optional

from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,field_validator

from app.services.chat_service import chat_service
from app.core.access import visitor_owner

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=2000)
    tts_enabled: bool = True
    tourist_id: str = "guest"
    interest: Optional[str] = Field(default=None,max_length=120)
    time_budget: Optional[str] = Field(default=None,max_length=80)
    companions: Optional[str] = Field(default=None,max_length=80)
    dialect: str = "mandarin"

    @field_validator('message')
    @classmethod
    def nonblank(cls,value):
        if not value.strip(): raise ValueError('message cannot be blank')
        return value.strip()


async def request_events(req, owner, request_id):
    """Keep outer failures compatible with the same SSE/HTTP request contract."""
    started=time.monotonic()
    text=''
    done=False
    try:
        async with aclosing(chat_service.stream_pipeline(query=req.message,tourist_id=owner,
            interest=req.interest,time_budget=req.time_budget,companions=req.companions,
            tts_enabled=req.tts_enabled,request_id=request_id)) as stream:
            async for event in stream:
                if event['type']=='delta': text+=event['text']
                if event['type']=='done': done=True
                yield event
    except asyncio.CancelledError: raise
    except Exception:
        if done: return
        yield {'type':'error','message':'请求未能完成，请重试。','partial':bool(text),'request_id':request_id}
        yield {'type':'done','status':'partial' if text else 'failed','full_text':text,
               'request_id':request_id,'latency_ms':round((time.monotonic()-started)*1000),
               'provenance':{'path':'route_error','model':None,'attempts':[],'switch_reason':'pipeline_error'},
               'timings':{'first_valid_text_ms':None,'first_actual_audio_ms':None,'total_ms':round((time.monotonic()-started)*1000,2)}}


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request, owner: str = Depends(visitor_owner)):
    """SSE流式对话:文本增量 + 情感标签 + 逐句语音与口型时间轴"""

    async def event_gen():
        async with aclosing(request_events(req,owner,request_id)) as stream:
            async for evt in stream:
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    request_id=getattr(request.state,'request_id',None) or uuid.uuid4().hex
    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/send")
async def chat_send(req: ChatRequest, request: Request, owner: str = Depends(visitor_owner)):
    """非流式兼容接口:聚合全部事件后一次性返回"""
    full_text, emotion, sources, intent = "", "calm", [], "general"
    request_id=getattr(request.state,'request_id',None) or uuid.uuid4().hex
    sentences, latency, status, evidence = [], 0, 'failed', {}
    async for evt in request_events(req,owner,request_id):
        if evt["type"] == "meta":
            sources, intent = evt["sources"], evt["intent"]
        elif evt["type"] == "emotion":
            emotion = evt["emotion"]
        elif evt["type"] == "sentence":
            sentences.append(evt)
        elif evt["type"] == "done":
            full_text, latency = evt["full_text"], evt["latency_ms"]
            status=evt['status']
            request_id=evt['request_id']
            evidence={k:evt.get(k) for k in ('provenance','timings','mode','knowledge_revision')}
    return {"answer": full_text, "emotion": emotion, "intent": intent,
            "sources": sources, "sentences": sentences, "latency_ms": latency,'status':status,'request_id':request_id,**evidence}


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
    image_b64: str = Field(max_length=4_000_000)
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
