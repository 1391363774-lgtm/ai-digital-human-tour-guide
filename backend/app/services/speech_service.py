from __future__ import annotations

import asyncio
import re
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
    # 类级别音频缓存：所有实例共享，key = "text|voice|rate"
    _audio_cache: dict[str, bytes] = {}
    # 预编码 base64 缓存，避免流式响应时重复编码
    _b64_cache: dict[str, str] = {}
    _cache_max_entries = 300

    def __init__(self) -> None:
        self.settings = get_settings()

    @classmethod
    def _cache_key(cls, text: str, voice: str, rate: float) -> str:
        # 统一 rate 格式，避免 1(int) vs 1.0(float) 导致缓存 key 不匹配
        return f"{text}|{voice}|{float(rate)}"

    @classmethod
    def _cache_get(cls, text: str, voice: str, rate: float) -> bytes | None:
        key = cls._cache_key(text, voice, rate)
        return cls._audio_cache.get(key)

    @classmethod
    def _b64_get(cls, text: str, voice: str, rate: float) -> str | None:
        """获取预编码的 base64 字符串，缓存未命中返回 None。"""
        key = cls._cache_key(text, voice, rate)
        return cls._b64_cache.get(key)

    @classmethod
    def _cache_put(cls, text: str, voice: str, rate: float, audio: bytes) -> None:
        if len(cls._audio_cache) >= cls._cache_max_entries:
            # 简单 LRU：移除最早的条目
            oldest_key = next(iter(cls._audio_cache))
            cls._audio_cache.pop(oldest_key, None)
            cls._b64_cache.pop(oldest_key, None)
        key = cls._cache_key(text, voice, rate)
        cls._audio_cache[key] = audio
        # 预编码 base64，流式响应时直接取用
        import base64 as _b64mod
        cls._b64_cache[key] = _b64mod.b64encode(audio).decode("ascii")

    async def synthesize_mp3(self, text: str, voice: str | None = None, rate: float = 1.0) -> bytes:
        clean_text = text.strip()
        if not clean_text:
            raise SpeechServiceError("TTS 文本不能为空")
        if len(clean_text) > 3000:
            clean_text = clean_text[:3000]

        selected_voice = voice or DEFAULT_EDGE_TTS_VOICE

        # 缓存命中 → 直接返回，无需网络请求
        cached = self._cache_get(clean_text, selected_voice, rate)
        if cached is not None:
            import sys
            print(f"[CACHE HIT] len={len(self._audio_cache)} key={clean_text[:20]}...|{selected_voice}|{rate}({type(rate).__name__})", file=sys.stderr, flush=True)
            return cached
        import sys
        print(f"[CACHE MISS] key={clean_text[:20]}...|{selected_voice}|{rate}({type(rate).__name__})", file=sys.stderr, flush=True)

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
            raise SpeechServiceError(f"edge-tts 语音合成失败：{exc}") from exc

        if not audio:
            raise SpeechServiceError("edge-tts 未返回有效音频")
        # 存入缓存
        self._cache_put(clean_text, selected_voice, rate, audio)
        return audio

    @staticmethod
    async def _collect_audio_chunks(communicate) -> list[bytes]:
        """从 edge_tts.Communicate.stream() 中收集所有音频 chunk。"""
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return chunks

    def _format_edge_rate(self, rate: float) -> str:
        percent = int(round((rate - 1.0) * 100))
        percent = max(-50, min(50, percent))
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
        clean = text.strip()
        if not clean:
            return []
        if len(clean) > 3000:
            clean = clean[:3000]

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
        if not segments:
            return []

        semaphore = asyncio.Semaphore(max_concurrency)

        async def synth_one(seg: str) -> bytes:
            async with semaphore:
                try:
                    return await self.synthesize_segment(seg, voice=voice, rate=rate)
                except SpeechServiceError:
                    raise
                except Exception as exc:
                    raise SpeechServiceError(f"分段合成失败：{exc}") from exc

        return await asyncio.gather(*[synth_one(s) for s in segments])

    async def synthesize_segments_streaming(
        self,
        segments: list[str],
        voice: str | None = None,
        rate: float = 1.0,
        first_batch_size: int = 1,
        max_concurrency: int = 5,
    ):
        """流式合成：先合成第一批段并逐个 yield，剩余段并行合成后按顺序 yield。

        返回 (index, text, audio_bytes) 元组的异步生成器。
        前端拿到第一批即可开始播放，同时后端并行合成后续段。
        """
        if not segments:
            return

        total = len(segments)
        first_count = min(first_batch_size, total)
        rest = segments[first_count:]

        # 第一批：逐个同步合成，立即 yield（让前端尽快开始播放）
        for i in range(first_count):
            audio = await self.synthesize_segment(segments[i], voice=voice, rate=rate)
            yield i, segments[i], audio

        if not rest:
            return

        # 剩余段：并行合成，用缓冲区保证按原始顺序 yield
        semaphore = asyncio.Semaphore(max_concurrency)

        async def synth_one(idx: int, seg: str) -> tuple[int, str, bytes]:
            async with semaphore:
                try:
                    return idx, seg, await self.synthesize_segment(seg, voice=voice, rate=rate)
                except SpeechServiceError:
                    raise
                except Exception as exc:
                    raise SpeechServiceError(f"分段合成失败：{exc}") from exc

        tasks = [
            asyncio.create_task(synth_one(first_count + i, seg))
            for i, seg in enumerate(rest)
        ]

        buffer: dict[int, tuple[str, bytes]] = {}
        next_yield = first_count

        for coro in asyncio.as_completed(tasks):
            idx, seg, audio = await coro
            buffer[idx] = (seg, audio)
            while next_yield in buffer:
                seg, audio = buffer.pop(next_yield)
                next_yield += 1
                yield next_yield - 1, seg, audio


async def prewarm_tts_cache(texts: list[str], voice: str = DEFAULT_EDGE_TTS_VOICE, rate: float = 1.0) -> int:
    """预合成热点文本的音频并缓存。返回成功预热的条数。

    在后端启动后异步执行，不影响启动速度。
    预热后对应文本的 TTS 请求将直接从缓存返回，延迟 < 50ms。
    使用并行合成（并发 8）加速预热过程。
    """
    svc = TtsService()

    # 收集所有需要预合成的段
    all_segments: list[str] = []
    for text in texts:
        segments = svc.split_text_segments(text, max_segment_chars=25)
        all_segments.extend(segments)

    total = len(all_segments)

    # 并行预合成，限制并发数
    semaphore = asyncio.Semaphore(8)

    async def synth_one(seg: str) -> int:
        async with semaphore:
            try:
                await svc.synthesize_segment(seg, voice=voice, rate=rate)
                return 1
            except SpeechServiceError:
                return 0
            except Exception:
                return 0

    results = await asyncio.gather(*[synth_one(seg) for seg in all_segments])
    success = sum(results)
    return success
