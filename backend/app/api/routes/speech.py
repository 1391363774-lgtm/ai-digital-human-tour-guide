from io import BytesIO
import asyncio
import logging
from contextlib import aclosing
from uuid import uuid4

import anyio

from fastapi import APIRouter, File, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from app.core.streaming import ClosingStreamingResponse
from app.core.config import get_settings

from app.schemas.response import success
from app.schemas.speech import AsrResponse, TtsRequest, TtsSegmentRequest
from app.services.speech_service import FasterWhisperAsrService, SpeechServiceError, TtsService

router = APIRouter(prefix="/api/speech", tags=["speech"])
logger = logging.getLogger(__name__)


async def until_disconnected(request, work):
    """A cancelled HTTP fetch must also stop synthesis before response headers exist."""
    task = asyncio.create_task(work)
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=0.1)
            if await request.is_disconnected():
                raise asyncio.CancelledError
        return task.result()
    finally:
        task.cancel()
        with anyio.CancelScope(shield=True):
            await asyncio.gather(task, return_exceptions=True)


@router.post("/asr")
def speech_to_text(file: UploadFile = File(...)):
    if get_settings().demo_mode:
        raise HTTPException(503, detail="离线演示不加载ASR模型，请用文字输入")
    try:
        result = FasterWhisperAsrService().transcribe_upload(file)
    except SpeechServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    data = AsrResponse(
        text=result.text,
        language=result.language,
        duration=result.duration,
        segments=[
            {"start": segment.start, "end": segment.end, "text": segment.text}
            for segment in result.segments
        ],
    )
    return success(data.model_dump())


@router.post("/tts")
async def text_to_speech(payload: TtsRequest, request: Request):
    try:
        audio = await until_disconnected(request, TtsService().synthesize_mp3(
            text=payload.text,
            voice=payload.voice,
            rate=payload.rate,
        ))
    except SpeechServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": 'inline; filename="scenic-guide-tts.wav"' if get_settings().demo_mode else 'inline; filename="scenic-guide-tts.mp3"',
        "Cache-Control": "no-store",
        "X-Request-ID": payload.request_id or uuid4().hex,
        "X-Segment-ID": payload.segment_id or "0",
    }
    return StreamingResponse(
        BytesIO(audio),
        media_type="audio/wav" if get_settings().demo_mode else "audio/mpeg",
        headers=headers,
    )


@router.post("/tts/segments")
async def text_to_speech_segments(payload: TtsSegmentRequest, request: Request):
    """分段 TTS：返回 JSON，包含切分后的文本段和每段的 base64 MP3 音频。"""
    import base64

    try:
        svc = TtsService()
        segments = svc.split_text_segments(payload.text, max_segment_chars=45)
        if not segments:
            raise HTTPException(status_code=400, detail="文本为空，无法合成语音")

        audio_list = await until_disconnected(request, svc.synthesize_segments_parallel(
            segments,
            voice=payload.voice,
            rate=payload.rate,
            max_concurrency=3,
        ))
    except SpeechServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = []
    for seg_text, audio_bytes in zip(segments, audio_list):
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        result.append({"text": seg_text, "audio_base64": b64, "size": len(audio_bytes)})

    return success({"segments": result, "total_segments": len(result)})


@router.post("/tts/stream")
async def text_to_speech_stream(payload: TtsSegmentRequest):
    """流式 TTS：返回 NDJSON 流，每行一个 JSON 对象。

    第一段立即合成并返回，前端拿到即可开始播放；
    后续段在后端并行合成，按顺序逐行返回。
    """
    import base64
    import json

    svc = TtsService()
    # 减小段长度至 25 字，降低未缓存时 edge-tts 单段合成时间
    segments = svc.split_text_segments(payload.text, max_segment_chars=25)
    if not segments:
        raise HTTPException(status_code=400, detail="文本为空，无法合成语音")

    total = len(segments)
    # 首批强制只合成 1 段，让首音以最快速度到达
    first_batch_size = 1
    selected_voice = payload.voice or "zh-CN-XiaoxiaoNeural"
    selected_rate = payload.rate if payload.rate is not None else 1.0
    request_id = payload.request_id or uuid4().hex

    async def generate():
        import time as _time
        t0 = _time.perf_counter()

        yield json.dumps(
            {"type": "meta", "total_segments": total, "request_id": request_id}, ensure_ascii=False
        ) + "\n"

        try:
            async with aclosing(svc.synthesize_segments_streaming(
                segments,
                voice=selected_voice,
                rate=selected_rate,
                first_batch_size=first_batch_size,
                max_concurrency=5,
            )) as stream:
              async for idx, seg_text, audio_bytes in stream:
                # 优先使用预编码的 base64（缓存命中时免去实时编码）
                b64 = svc._b64_get(seg_text.strip(), selected_voice, selected_rate)
                if b64 is None:
                    b64 = base64.b64encode(audio_bytes).decode("ascii")
                yield json.dumps(
                    {
                        "type": "segment",
                        "index": idx,
                        "request_id": request_id,
                        "segment_id": f"{payload.segment_id or '0'}:{idx}",
                        "text": seg_text,
                        "audio_base64": b64,
                        "size": len(audio_bytes),
                    },
                    ensure_ascii=False,
                ) + "\n"
                if idx == 0:
                    logger.info("tts_first_segment request_id=%s duration_ms=%s", request_id, int((_time.perf_counter()-t0)*1000))
        except Exception as exc:
            logger.warning("tts_stream_failed request_id=%s error_type=%s", request_id, type(exc).__name__)
            yield json.dumps(
                {"type": "error", "message": "语音合成失败，请使用文字阅读", "request_id": request_id}, ensure_ascii=False
            ) + "\n"
            return

        yield json.dumps(
            {"type": "done", "total_segments": total, "request_id": request_id}, ensure_ascii=False
        ) + "\n"

    return ClosingStreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )
