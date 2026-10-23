"""
TTS 语音合成 + 中文视素(Viseme)口型时间轴服务
------------------------------------------------
核心原理:
  edge-tts 合成神经语音的同时产出"词边界(WordBoundary)"事件,
  精确到每个词在音频中的起止时间;再将每个汉字转拼音,
  声母/韵母映射为中文视素口型,生成与音频毫秒级对齐的口型时间轴。

  音频 ──┐
         ├─► 前端数字人按时间轴驱动口型 → 口型与发音严格同步
  时间轴 ─┘
"""
import hashlib
import re
import secrets
import time
import asyncio
import math
import struct
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pypinyin import lazy_pinyin, Style

from app.core.config import settings

# ============================================================
# 中文视素集(12种口型,覆盖普通话全部发音)
# ============================================================
# 韵母 → 主导口型
FINAL_VISEME = {
    "a": "AA", "ia": "AA", "ua": "AA",
    "o": "OO", "uo": "OO", "ao": "OO", "iao": "OO", "ong": "OO", "iong": "OO",
    "e": "EH", "ie": "EH", "er": "EH", "ue": "EH", "ve": "EH",
    "i": "II", "ian": "II", "in": "II", "ing": "II", "iang": "AA",
    "u": "UU", "uan": "UU", "un": "UU", "uang": "AA",
    "v": "UU", "vn": "UU", "van": "UU",
    "ai": "AA", "uai": "AA",
    "ei": "EH", "ui": "EH", "uei": "EH",
    "ou": "OO", "iu": "II", "iou": "II",
    "an": "AA", "en": "EH", "ang": "AA", "eng": "EH",
    "io": "OO",
}
# 声母 → 起始口型
INITIAL_VISEME = {
    "b": "MM", "p": "MM", "m": "MM",          # 双唇闭合
    "f": "FF",                                  # 上齿咬下唇
    "d": "DD", "t": "DD", "n": "DD", "l": "DD",  # 舌尖抵龈
    "g": "KK", "k": "KK", "h": "KK",            # 软腭微开
    "j": "SS", "q": "SS", "x": "SS",            # 齿间窄缝
    "zh": "RR", "ch": "RR", "sh": "RR", "r": "RR",  # 翘舌圆展
    "z": "SS", "c": "SS", "s": "SS",            # 平舌齿缝
    "y": "II", "w": "UU",                       # 半元音
}
PUNCT_PAUSE_MS = {"，": 180, "、": 160, "。": 320, "！": 320, "？": 320,
                  "；": 240, "：": 240, ",": 180, ".": 320, "!": 320, "?": 320,
                  ";": 240, ":": 240, "~": 150, "—": 120, "…": 300}


def _char_visemes(char: str) -> Tuple[Optional[str], str]:
    """单字 → (声母口型, 韵母口型)"""
    py = lazy_pinyin(char, style=Style.NORMAL, errors="ignore")
    if not py:
        return None, "sil"
    syllable = py[0]
    initials = lazy_pinyin(char, style=Style.INITIALS, errors="ignore")
    initial = initials[0] if initials else ""
    final = syllable[len(initial):] if initial and syllable.startswith(initial) else syllable
    # pypinyin 的 ü 写作 v,兼容处理
    final = final.replace("ü", "v")
    iv = INITIAL_VISEME.get(initial)
    fv = FINAL_VISEME.get(final, "AA")
    return iv, fv


def build_viseme_timeline(word_boundaries: List[Dict], total_ms: int) -> List[Dict]:
    """
    词边界 → 口型时间轴
    word_boundaries: [{text, offset_ms, duration_ms}]
    返回: [{t: 起始毫秒, v: 口型, d: 持续毫秒}] 已合并相邻同型
    """
    events: List[Dict] = []
    for wb in word_boundaries:
        text = wb["text"]
        chars = [c for c in text if not c.isspace()]
        if not chars:
            continue
        offset = wb["offset_ms"]
        dur = max(wb["duration_ms"], 60)
        per_char = dur / len(chars)
        for i, ch in enumerate(chars):
            ch_start = offset + i * per_char
            iv, fv = _char_visemes(ch)
            if iv and iv != fv:
                init_dur = per_char * 0.38
                events.append({"t": round(ch_start, 1), "v": iv, "d": round(init_dur, 1)})
                events.append({"t": round(ch_start + init_dur, 1), "v": fv,
                               "d": round(per_char - init_dur, 1)})
            else:
                events.append({"t": round(ch_start, 1), "v": fv, "d": round(per_char, 1)})

    # 合并相邻同型 & 排序
    events.sort(key=lambda e: e["t"])
    merged: List[Dict] = []
    for e in events:
        if merged and merged[-1]["v"] == e["v"] and \
                abs(merged[-1]["t"] + merged[-1]["d"] - e["t"]) < 40:
            merged[-1]["d"] = round(e["t"] + e["d"] - merged[-1]["t"], 1)
        else:
            merged.append(dict(e))
    # 收尾闭口
    if merged:
        merged.append({"t": float(total_ms), "v": "sil", "d": 0.0})
    return merged


def estimate_timeline_offline(text: str, chars_per_sec: float = 5.2) -> Tuple[List[Dict], int]:
    """
    无TTS词边界时的降级方案:按语速估算时间轴
    (浏览器speechSynthesis兜底播放时使用,口型依然逐字同步)
    """
    events: List[Dict] = []
    t = 0.0
    ms_per_char = 1000.0 / chars_per_sec
    for ch in text:
        if ch in PUNCT_PAUSE_MS:
            pause = PUNCT_PAUSE_MS[ch]
            events.append({"t": round(t, 1), "v": "sil", "d": float(pause)})
            t += pause
            continue
        if ch.isspace() or ord(ch) < 0x2E80:  # 非CJK字符快速带过
            t += ms_per_char * 0.4
            continue
        iv, fv = _char_visemes(ch)
        init_dur = ms_per_char * 0.38
        if iv and iv != fv:
            events.append({"t": round(t, 1), "v": iv, "d": round(init_dur, 1)})
            events.append({"t": round(t + init_dur, 1), "v": fv,
                           "d": round(ms_per_char - init_dur, 1)})
        else:
            events.append({"t": round(t, 1), "v": fv, "d": round(ms_per_char, 1)})
        t += ms_per_char
    events.append({"t": round(t, 1), "v": "sil", "d": 0.0})
    # 合并
    merged: List[Dict] = []
    for e in events:
        if merged and merged[-1]["v"] == e["v"]:
            merged[-1]["d"] = round(merged[-1]["d"] + e["d"], 1)
        else:
            merged.append(dict(e))
    return merged, int(t)


# ============================================================
# TTS 合成服务
# ============================================================
class TtsService:
    def __init__(self):
        self.cache_dir = Path(settings.TTS_CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._inflight = {}
        self._slots = asyncio.Semaphore(3)

    def _cache_key(self, text: str, voice: str) -> str:
        return hashlib.md5(f"word-pinyin-estimate-v2|{settings.DEMO_MODE}|{voice}|{settings.TTS_RATE}|{settings.TTS_PITCH}|{text}".encode("utf-8")).hexdigest()

    async def synthesize(self, text: str, voice: Optional[str] = None) -> Dict:
        text=text.strip()[:800]
        if not text: return {'ok':False,'reason':'empty text'}
        voice=voice or settings.TTS_VOICE
        key=self._cache_key(text,voice)
        entry=self._inflight.get(key)
        if entry is None:
            if len(self._inflight)>=64: return {'ok':False,'reason':'speech capacity reached'}
            entry={'task':asyncio.create_task(self._limited_synthesize(text,voice)), 'waiters':0}
            self._inflight[key]=entry
        entry['waiters']+=1
        try:
            return dict(await asyncio.shield(entry['task']))
        finally:
            entry['waiters']-=1
            if entry['waiters']==0:
                if not entry['task'].done(): entry['task'].cancel()
                await asyncio.gather(entry['task'],return_exceptions=True)
                if self._inflight.get(key) is entry: self._inflight.pop(key,None)

    async def _limited_synthesize(self,text,voice):
        from starlette.concurrency import run_in_threadpool
        async with self._slots:
            await run_in_threadpool(self._prune_cache)
            if settings.DEMO_MODE:
                return await run_in_threadpool(self._demo_tone,text,voice)
            try:
                return await asyncio.wait_for(self._synthesize_cached(text,voice),timeout=10)
            except asyncio.TimeoutError:
                return {'ok':False,'reason':'speech timeout'}

    def _prune_cache(self):
        files=[p for p in self.cache_dir.iterdir() if p.suffix in ('.mp3','.json','.wav') and re.fullmatch('[a-f0-9]{32}',p.stem)]
        files.sort(key=lambda p:p.stat().st_mtime)
        for i,p in enumerate(files):
            if i<len(files)-512 or time.time()-p.stat().st_mtime>86400:
                p.unlink(missing_ok=True)

    def _demo_tone(self,text,voice):
        key=self._cache_key(text,voice)
        path=self.cache_dir/(key+'.wav')
        if not path.exists():
            with wave.open(str(path),'wb') as audio:
                audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(8000)
                audio.writeframes(b''.join(struct.pack('<h',int(1400*math.sin(2*math.pi*440*i/8000))) for i in range(2000)))
        return {'ok':True,'engine':'demo-tone','audio_url':f'/api/tts/audio/{key}','duration_ms':250,'visemes':[{'t':0,'v':'AA','d':250},{'t':250,'v':'sil','d':0}],'mouth_alignment':'synthetic_demo','cached':False}

    async def _synthesize_cached(self, text: str, voice: Optional[str] = None) -> Dict:
        """
        合成语音并生成口型时间轴。
        返回: {ok, audio_url, duration_ms, visemes, engine}
        失败(断网等)时 ok=False,前端自动降级浏览器TTS+估算时间轴。
        """
        voice = voice or settings.TTS_VOICE
        key = self._cache_key(text, voice)
        mp3_path = self.cache_dir / f"{key}.mp3"
        meta_path = self.cache_dir / f"{key}.json"

        # 命中缓存
        if mp3_path.exists() and meta_path.exists():
            import json as _json
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            meta["audio_url"] = f"/api/tts/audio/{key}"
            meta["cached"] = True
            return meta

        try:
            import edge_tts
        except ImportError:
            return {"ok": False, "reason": "edge-tts未安装"}

        word_boundaries: List[Dict] = []
        try:
            communicate = edge_tts.Communicate(
                text, voice, rate=settings.TTS_RATE, pitch=settings.TTS_PITCH, boundary='WordBoundary')
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # edge-tts时间单位为100纳秒
                    word_boundaries.append({
                        "text": chunk["text"],
                        "offset_ms": chunk["offset"] / 10000.0,
                        "duration_ms": chunk["duration"] / 10000.0,
                    })
            if not audio_chunks:
                return {"ok": False, "reason": "TTS无音频返回"}
            mp3_path.write_bytes(b"".join(audio_chunks))
        except Exception as e:
            print(f"[TTS] 合成失败: {type(e).__name__}")
            return {"ok": False, "reason": "语音服务暂不可用"}

        # 估算总时长(mp3 24kbps约3KB/s;用词边界末端更准)
        if word_boundaries:
            total_ms = int(max(wb["offset_ms"] + wb["duration_ms"] for wb in word_boundaries)) + 200
        else:
            total_ms = int(mp3_path.stat().st_size / 3000 * 1000)
        visemes = build_viseme_timeline(word_boundaries, total_ms) if word_boundaries \
            else estimate_timeline_offline(text)[0]

        meta = {
            "ok": True, "engine": "edge-tts", "voice": voice,
            "audio_url": f"/api/tts/audio/{key}",
            "duration_ms": total_ms, "visemes": visemes, "cached": False,
            'mouth_alignment':'word_boundary_pinyin_estimate' if word_boundaries else 'text_duration_estimate',
        }
        import json as _json
        meta_path.write_text(_json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return meta

    def audio_path(self, key: str) -> Optional[Path]:
        if not re.fullmatch(r'[a-f0-9]{32}',key):
            return None
        p = self.cache_dir / f"{key}.mp3"
        if settings.DEMO_MODE and (self.cache_dir/f'{key}.wav').exists():
            p=self.cache_dir/f'{key}.wav'
        return p if p.exists() else None

    def grant_audio(self, meta: Dict) -> Dict:
        result = dict(meta)
        url = result.get('audio_url')
        if not url:
            return result
        if not hasattr(self, '_grants'):
            self._grants = {}
        now = time.monotonic()
        self._grants = {k:v for k,v in self._grants.items() if v[1] > now}
        if len(self._grants) >= 256:
            self._grants.pop(next(iter(self._grants)))
        token = secrets.token_urlsafe(24)
        self._grants[token] = (url.rsplit('/',1)[-1], now + 300)
        result['audio_url'] = url + '?access=' + token
        return result

    def authorized_audio(self, key, token):
        grant = getattr(self, '_grants', {}).get(token or '')
        if not grant or grant[0] != key or grant[1] < time.monotonic():
            return None
        return self.audio_path(key)


tts_service = TtsService()
