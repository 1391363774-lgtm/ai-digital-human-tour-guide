from io import BytesIO

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.schemas.response import success
from app.schemas.speech import AsrResponse, TtsRequest
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
