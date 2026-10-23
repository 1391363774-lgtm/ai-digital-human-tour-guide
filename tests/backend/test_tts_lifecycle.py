import asyncio
import pytest
from app.services.tts_service import TtsService,build_viseme_timeline


def test_duplicate_synthesis_is_single_flight_and_limited(tmp_path,monkeypatch):
    service=TtsService(); service.cache_dir=tmp_path
    async def run():
        calls=active=peak=0
        async def fake(text,voice):
            nonlocal calls,active,peak
            calls+=1; active+=1; peak=max(peak,active)
            try: await asyncio.sleep(0.02); return {'ok':True}
            finally: active-=1
        monkeypatch.setattr(service,'_synthesize_cached',fake)
        await asyncio.gather(*[service.synthesize('same') for _ in range(6)])
        assert calls==1
        await asyncio.gather(*[service.synthesize(str(i)) for i in range(9)])
        assert peak<=3 and not service._inflight
    asyncio.run(run())


def test_cancelling_last_waiter_cleans_provider_task(tmp_path,monkeypatch):
    service=TtsService(); service.cache_dir=tmp_path
    async def run():
        started=asyncio.Event(); closed=asyncio.Event()
        async def fake(*args):
            started.set()
            try: await asyncio.Event().wait()
            finally: closed.set()
        monkeypatch.setattr(service,'_synthesize_cached',fake)
        task=asyncio.create_task(service.synthesize('cancel'))
        await started.wait(); task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert closed.is_set() and not service._inflight
    asyncio.run(run())


def test_cache_identity_includes_rate_pitch_and_demo(monkeypatch):
    from app.core.config import settings
    service=TtsService()
    key=service._cache_key('same','same')
    monkeypatch.setattr(settings,'TTS_RATE','+30%')
    assert key!=service._cache_key('same','same')


def test_demo_is_explicit_synthetic_audio_without_network(tmp_path,monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings,'DEMO_MODE',True)
    service=TtsService(); service.cache_dir=tmp_path
    result=asyncio.run(service.synthesize('仅为测试音'))
    assert result['engine']=='demo-tone' and result['mouth_alignment']=='synthetic_demo'
    assert service.audio_path(result['audio_url'].rsplit('/',1)[-1]).read_bytes().startswith(b'RIFF')


def test_word_boundary_timeline_is_estimated_from_characters():
    result=build_viseme_timeline([{'text':'大佛','offset_ms':100,'duration_ms':400}],600)
    assert result[0]['t']==100 and result[-1]['v']=='sil'
    assert all(e['t']<=600 for e in result)
