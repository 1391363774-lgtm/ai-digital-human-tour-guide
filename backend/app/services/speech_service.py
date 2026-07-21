from __future__ import annotations

import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings

ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac"}
MAX_AUDIO_SIZE = 20 * 1024 * 1024
DEFAULT_EDGE_TTS_VOICE = "zh-CN-XiaoxiaoNeural"


@dataclass(frozen=True)
class AsrSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class AsrResult:
    text: str
    language: str | None
    duration: float | None
    segments: list[AsrSegment]


class SpeechServiceError(RuntimeError):
    pass


class FasterWhisperAsrService:
    _model = None

    def __init__(self) -> None:
        self.settings = get_settings()

    def transcribe_upload(self, file: UploadFile) -> AsrResult:
        audio_path = save_upload_audio(file)
        try:
            return self.transcribe_file(audio_path)
        finally:
            audio_path.unlink(missing_ok=True)

    def transcribe_file(self, audio_path: str | Path) -> AsrResult:
        model = self._get_model()
        try:
            segments_iter, info = model.transcribe(
                str(audio_path),
                beam_size=1,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )
            segments = [
                AsrSegment(start=item.start, end=item.end, text=item.text.strip())
                for item in segments_iter
                if item.text.strip()
            ]
        except Exception as exc:
            raise SpeechServiceError(f"语音识别失败：{exc}") from exc

        return AsrResult(
            text="".join(segment.text for segment in segments).strip(),
            language=getattr(info, "language", None),
            duration=getattr(info, "duration", None),
            segments=segments,
        )

    def _get_model(self):
        if FasterWhisperAsrService._model is not None:
            return FasterWhisperAsrService._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise SpeechServiceError(
                "缺少 faster-whisper 依赖，后端暂不能语音识别；前端会尝试浏览器语音识别或回退文本输入。"
            ) from exc

        try:
            FasterWhisperAsrService._model = WhisperModel(
                self.settings.asr_model_size,
                device=self.settings.asr_device,
                compute_type=self.settings.asr_compute_type,
            )
        except Exception as exc:
            raise SpeechServiceError(
                "语音模型正在下载或加载中，首次运行预计需要几分钟；"
                f"如果长时间失败，请检查网络和模型缓存。原始错误：{exc}"
            ) from exc

        return FasterWhisperAsrService._model


def save_upload_audio(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise SpeechServiceError(f"暂不支持的音频格式：{suffix or '未知'}")

    size = 0
    target = Path(tempfile.gettempdir()) / f"scenic_asr_{uuid.uuid4().hex}{suffix}"
    with target.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_AUDIO_SIZE:
                target.unlink(missing_ok=True)
                raise SpeechServiceError("音频文件超过 20MB 限制")
            output.write(chunk)
    return target


class TtsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def synthesize_mp3(self, text: str, voice: str | None = None, rate: float = 1.0) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise SpeechServiceError("TTS 文本不能为空")
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000]

        selected_voice = voice or DEFAULT_EDGE_TTS_VOICE
        try:
            import edge_tts
        except ImportError as exc:
            raise SpeechServiceError("缺少 edge-tts 依赖，无法生成后端语音") from exc

        try:
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=selected_voice,
                rate=self._format_edge_rate(rate),
            )
            chunks: list[bytes] = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            audio = b"".join(chunks)
        except Exception as exc:
            raise SpeechServiceError(f"edge-tts 语音合成失败：{exc}") from exc

        if not audio:
            raise SpeechServiceError("edge-tts 未返回有效音频")
        return audio

    def _format_edge_rate(self, rate: float) -> str:
        percent = int(round((rate - 1.0) * 100))
        percent = max(-50, min(50, percent))
        return f"{percent:+d}%"
