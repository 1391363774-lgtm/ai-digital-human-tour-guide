"""
TTS语音合成API
POST /api/tts          文本→语音+口型时间轴
GET  /api/tts/audio/{key}  音频文件
GET  /api/tts/voices   可用音色列表
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.services.tts_service import tts_service, estimate_timeline_offline

router = APIRouter()


class TtsRequest(BaseModel):
    text: str
    voice: str | None = None


@router.post("")
async def synthesize(req: TtsRequest):
    if not req.text.strip():
        raise HTTPException(400, "文本不能为空")
    if len(req.text) > 800:
        req.text = req.text[:800]
    return tts_service.grant_audio(await tts_service.synthesize(req.text.strip(), req.voice))


@router.post("/timeline")
async def timeline_only(req: TtsRequest):
    """仅生成估算口型时间轴(浏览器TTS兜底时前端调用)"""
    visemes, total = estimate_timeline_offline(req.text.strip())
    return {"ok": True, "engine": "estimate", "duration_ms": total, "visemes": visemes}


@router.get("/audio/{key}")
async def get_audio(key: str, access: str = ''):
    path = tts_service.authorized_audio(key, access)
    if not path:
        raise HTTPException(404, "音频不存在")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/voices")
async def list_voices():
    return {
        "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓(温柔女声·默认)", "gender": "女"},
            {"id": "zh-CN-XiaoyiNeural", "name": "晓伊(活泼女声)", "gender": "女"},
            {"id": "zh-CN-YunjianNeural", "name": "云健(沉稳男声)", "gender": "男"},
            {"id": "zh-CN-YunxiNeural", "name": "云希(清朗男声)", "gender": "男"},
        ],
        "default": settings.TTS_VOICE,
    }
