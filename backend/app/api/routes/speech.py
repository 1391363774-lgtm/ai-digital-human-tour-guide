from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.response import success
from app.schemas.speech import AsrResponse, TtsRequest, TtsSegmentRequest
from app.services.speech_service import FasterWhisperAsrService, SpeechServiceError, TtsService

router = APIRouter(prefix="/api/speech", tags=["speech"])


@router.post("/asr")
def speech_to_text(file: UploadFile = File(...)):
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
async def text_to_speech(payload: TtsRequest):
    try:
        audio = await TtsService().synthesize_mp3(
            text=payload.text,
            voice=payload.voice,
            rate=payload.rate,
        )
    except SpeechServiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    headers = {
        "Content-Disposition": 'inline; filename="scenic-guide-tts.mp3"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(
        BytesIO(audio),
        media_type="audio/mpeg",
        headers=headers,
    )


@router.post("/tts/segments")
async def text_to_speech_segments(payload: TtsSegmentRequest):
    """分段 TTS：返回 JSON，包含切分后的文本段和每段的 base64 MP3 音频。"""
    import base64

    try:
        svc = TtsService()
        segments = svc.split_text_segments(payload.text, max_segment_chars=45)
        if not segments:
            raise HTTPException(status_code=400, detail="文本为空，无法合成语音")

        audio_list = await svc.synthesize_segments_parallel(
            segments,
            voice=payload.voice,
            rate=payload.rate,
            max_concurrency=3,
        )
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

    async def generate():
        import time as _time
        t0 = _time.perf_counter()

        yield json.dumps(
            {"type": "meta", "total_segments": total}, ensure_ascii=False
        ) + "\n"

        try:
            async for idx, seg_text, audio_bytes in svc.synthesize_segments_streaming(
                segments,
                voice=selected_voice,
                rate=selected_rate,
                first_batch_size=first_batch_size,
                max_concurrency=5,
            ):
                # 优先使用预编码的 base64（缓存命中时免去实时编码）
                b64 = svc._b64_get(seg_text.strip(), selected_voice, selected_rate)
                if b64 is None:
                    b64 = base64.b64encode(audio_bytes).decode("ascii")
                yield json.dumps(
                    {
                        "type": "segment",
                        "index": idx,
                        "text": seg_text,
                        "audio_base64": b64,
                        "size": len(audio_bytes),
                    },
                    ensure_ascii=False,
                ) + "\n"
                if idx == 0:
                    import sys
                    print(f"[TTS STREAM] first_seg_ms={int((_time.perf_counter()-t0)*1000)}", file=sys.stderr, flush=True)
        except SpeechServiceError as exc:
            yield json.dumps(
                {"type": "error", "message": str(exc)}, ensure_ascii=False
            ) + "\n"
            return

        yield json.dumps(
            {"type": "done", "total_segments": total}, ensure_ascii=False
        ) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-store"},
    )
