from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import math
import re
import tempfile
import uuid
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

import anyio
from fastapi import UploadFile

from app.core.config import get_settings

ALLOWED_AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".webm", ".ogg", ".flac"}
MAX_AUDIO_SIZE = 20 * 1024 * 1024
DEFAULT_EDGE_TTS_VOICE = "zh-CN-XiaoxiaoNeural"
MAX_TTS_TEXT_CHARS = 3000
MAX_TTS_AUDIO_BYTES = 12 * 1024 * 1024
logger = logging.getLogger(__name__)


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
            logger.warning("asr_failed error_type=%s", type(exc).__name__)
            raise SpeechServiceError("语音识别失败，请重试或使用文字输入") from exc

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
            logger.warning("asr_model_unavailable error_type=%s", type(exc).__name__)
            raise SpeechServiceError(
                "语音模型正在下载或加载中，首次运行预计需要几分钟；"
                "如果长时间失败，请检查网络和模型缓存。"
            ) from exc

        return FasterWhisperAsrService._model


def save_upload_audio(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_AUDIO_SUFFIXES:
        raise SpeechServiceError(f"暂不支持的音频格式：{suffix or '未知'}")

    size = 0
    target = Path(tempfile.gettempdir()) / f"scenic_asr_{uuid.uuid4().hex}{suffix}"
    try:
        with target.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_AUDIO_SIZE:
                    raise SpeechServiceError("音频文件超过 20MB 限制")
                output.write(chunk)
        if not size:
            raise SpeechServiceError("音频文件为空")
    except BaseException:
        # On Windows a live file handle cannot be unlinked. Leave the with block first.
        target.unlink(missing_ok=True)
        raise
    return target


class TtsService:
    # 每进程共享的 FIFO 缓存（不是 LRU）；不保存到磁盘，不在日志记录文本。
    _audio_cache: dict[str, bytes] = {}
    # 预编码 base64 缓存，避免流式响应时重复编码
    _b64_cache: dict[str, str] = {}
    _cache_max_entries = 300
    _cache_max_bytes = 32 * 1024 * 1024  # audio + base64 payload, excluding Python object overhead
    _cache_lock = RLock()

    def __init__(self) -> None:
        self.settings = get_settings()

    @classmethod
    def _cache_key(cls, text: str, voice: str, rate: float) -> str:
        # 统一 rate 格式，避免 1(int) vs 1.0(float) 导致缓存 key 不匹配
        return hashlib.sha256(f"{text}|{voice}|{float(rate)}".encode("utf-8")).hexdigest()

    @classmethod
    def _cache_get(cls, text: str, voice: str, rate: float) -> bytes | None:
        key = cls._cache_key(text, voice, rate)
        with cls._cache_lock:
            return cls._audio_cache.get(key)

    @classmethod
    def _b64_get(cls, text: str, voice: str, rate: float) -> str | None:
        """获取预编码的 base64 字符串，缓存未命中返回 None。"""
        key = cls._cache_key(text, voice, rate)
        with cls._cache_lock:
            return cls._b64_cache.get(key)

    @classmethod
    def _cache_put(cls, text: str, voice: str, rate: float, audio: bytes) -> None:
        key = cls._cache_key(text, voice, rate)
        encoded = base64.b64encode(audio).decode("ascii")
        item_size = len(audio) + len(encoded)
        with cls._cache_lock:
            if item_size > cls._cache_max_bytes:
                return
            cls._audio_cache.pop(key, None)
            cls._b64_cache.pop(key, None)
            used = sum(len(value) for value in cls._audio_cache.values()) + sum(len(value) for value in cls._b64_cache.values())
            while cls._audio_cache and (len(cls._audio_cache) >= cls._cache_max_entries or used + item_size > cls._cache_max_bytes):
                oldest_key = next(iter(cls._audio_cache))
                used -= len(cls._audio_cache.pop(oldest_key)) + len(cls._b64_cache.pop(oldest_key, ""))
            cls._audio_cache[key] = audio
            cls._b64_cache[key] = encoded

    @staticmethod
    def _validate_text(text: str) -> str:
        if not text.strip():
            raise SpeechServiceError("TTS 文本不能为空")
        if len(text) > MAX_TTS_TEXT_CHARS:
            raise SpeechServiceError("TTS 文本超过 3000 字符限制，请分段请求")
        return text.strip()

    async def synthesize_mp3(self, text: str, voice: str | None = None, rate: float = 1.0) -> bytes:
        clean_text = self._validate_text(text)
        formatted_rate = self._format_edge_rate(rate)
        if self.settings.demo_mode:
            from app.services.demo_service import demo_audio
            return demo_audio(clean_text, rate)

        selected_voice = voice or DEFAULT_EDGE_TTS_VOICE

        # 缓存命中 → 直接返回，无需网络请求
        cached = self._cache_get(clean_text, selected_voice, rate)
        if cached is not None:
            logger.debug("tts_cache_hit chars=%d", len(clean_text))
            return cached
        logger.debug("tts_cache_miss chars=%d", len(clean_text))

        try:
            import edge_tts
        except ImportError as exc:
            raise SpeechServiceError("缺少 edge-tts 依赖，无法生成后端语音") from exc

        try:
            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=selected_voice,
                rate=formatted_rate,
            )
            try:
                chunks = await asyncio.wait_for(
                    self._collect_audio_chunks(communicate), timeout=15.0
                )
            except asyncio.TimeoutError:
                raise SpeechServiceError("edge-tts 语音合成超时（15秒），请稍后重试")
            audio = b"".join(chunks)
        except SpeechServiceError:
            raise
        except Exception as exc:
            logger.warning("tts_provider_failed error_type=%s", type(exc).__name__)
            raise SpeechServiceError("语音合成失败，请重试或使用文字阅读") from exc

        if not audio:
            raise SpeechServiceError("edge-tts 未返回有效音频")
        # 存入缓存
        self._cache_put(clean_text, selected_voice, rate, audio)
        return audio

    @staticmethod
    async def _collect_audio_chunks(communicate) -> list[bytes]:
        """只收集音频；未消费的词边界不代表已实现音素或嘴形同步。"""
        chunks: list[bytes] = []
        size = 0
        stream = communicate.stream()
        try:
            async for chunk in stream:
                if chunk["type"] == "audio":
                    size += len(chunk["data"])
                    if size > MAX_TTS_AUDIO_BYTES:
                        raise SpeechServiceError("生成的音频超过大小限制，请缩短文本")
                    chunks.append(chunk["data"])
        finally:
            with anyio.CancelScope(shield=True):
                await stream.aclose()
        return chunks

    def _format_edge_rate(self, rate: float) -> str:
        if not math.isfinite(rate) or not 0.5 <= rate <= 1.5:
            raise SpeechServiceError("语速必须为 0.5 到 1.5 之间的有限数值")
        percent = int(round((rate - 1.0) * 100))
        return f"{percent:+d}%"

    # ---- 分段流式合成 ----

    @staticmethod
    def split_text_segments(text: str, max_segment_chars: int = 35) -> list[str]:
        """将文本按标点切分为适合流式 TTS 的小段。

        策略：
        1. 先按句号/问号/感叹号/换行切分
        2. 如果某段仍超过 max_segment_chars，再按逗号/分号切分
        3. 如果仍超长，硬切分
        """
        if not 1 <= max_segment_chars <= MAX_TTS_TEXT_CHARS:
            raise SpeechServiceError("分段长度不合法")
        clean = text.strip()
        if not clean:
            return []
        TtsService._validate_text(text)

        # 按句末标点切分
        raw_sentences = re.split(r'(?<=[。！？\n])', clean)
        sentences: list[str] = []
        for s in raw_sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) <= max_segment_chars:
                sentences.append(s)
            else:
                # 按逗号/分号再切
                parts = re.split(r'(?<=[，；,;])', s)
                buf = ""
                for p in parts:
                    p = p.strip()
                    if not p:
                        continue
                    if len(buf) + len(p) <= max_segment_chars:
                        buf += p
                    else:
                        if buf:
                            sentences.append(buf)
                        # 单段仍超长则硬切
                        while len(p) > max_segment_chars:
                            sentences.append(p[:max_segment_chars])
                            p = p[max_segment_chars:]
                        buf = p
                if buf:
                    sentences.append(buf)

        return sentences if sentences else [clean]

    async def synthesize_segment(
        self, text: str, voice: str | None = None, rate: float = 1.0
    ) -> bytes:
        """合成单段文本，返回 MP3 bytes。"""
        return await self.synthesize_mp3(text, voice=voice, rate=rate)

    async def synthesize_segments_parallel(
        self,
        segments: list[str],
        voice: str | None = None,
        rate: float = 1.0,
        max_concurrency: int = 5,
    ) -> list[bytes]:
        """并行合成多段文本，返回与 segments 对应的 MP3 bytes 列表。"""
        async with aclosing(self.synthesize_segments_streaming(
            segments, voice=voice, rate=rate, first_batch_size=0, max_concurrency=max_concurrency,
        )) as stream:
            return [audio async for _, _, audio in stream]

    async def synthesize_segments_streaming(
        self,
        segments: list[str],
        voice: str | None = None,
        rate: float = 1.0,
        first_batch_size: int = 1,
        max_concurrency: int = 5,
    ):
        """有界窗口预取，按原序返回；消费者停止时取消并等待所有子任务。

        最多 max_concurrency 个在途／已完成待消费段，慢消费者不会无限堆积音频。
        """
        if not 1 <= max_concurrency <= 8 or first_batch_size < 0:
            raise SpeechServiceError("语音并发参数不合法")
        if not segments:
            return

        total = len(segments)
        first_count = min(first_batch_size, total)

        # 第一批：逐个同步合成，立即 yield（让前端尽快开始播放）
        for i in range(first_count):
            audio = await self.synthesize_segment(segments[i], voice=voice, rate=rate)
            yield i, segments[i], audio

        pending: dict[int, asyncio.Task] = {}
        next_start = first_count
        try:
            for index in range(first_count, total):
                while next_start < total and len(pending) < max_concurrency:
                    pending[next_start] = asyncio.create_task(
                        self.synthesize_segment(segments[next_start], voice=voice, rate=rate),
                        name=f"tts-segment-{next_start}",
                    )
                    next_start += 1
                audio = await pending[index]
                del pending[index]
                yield index, segments[index], audio
        except SpeechServiceError:
            raise
        except Exception as exc:
            logger.warning("tts_segment_failed error_type=%s", type(exc).__name__)
            raise SpeechServiceError("分段语音合成失败，请重试") from exc
        finally:
            for task in pending.values():
                task.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(*pending.values(), return_exceptions=True)


async def prewarm_tts_cache(texts: list[str], voice: str = DEFAULT_EDGE_TTS_VOICE, rate: float = 1.0) -> int:
    """预合成热点文本的音频并缓存。返回成功预热的条数。

    在后端启动后异步执行，不影响启动速度。
    预热后对应文本的 TTS 请求可直接从进程内缓存返回，不保证固定延迟。
    使用并行合成（并发 8）加速预热过程。
    """
    svc = TtsService()

    # 收集所有需要预合成的段
    all_segments: list[str] = []
    for text in texts:
        segments = svc.split_text_segments(text, max_segment_chars=25)
        all_segments.extend(segments)

    async def synth_one(seg: str) -> int:
        try:
            await svc.synthesize_segment(seg, voice=voice, rate=rate)
            return 1
        except Exception:
            return 0

    success = 0
    for offset in range(0, len(all_segments), 8):
        success += sum(await asyncio.gather(*[synth_one(seg) for seg in all_segments[offset:offset + 8]]))
    return success
