import asyncio
from fastapi import FastAPI
import httpx
import pytest
from starlette.requests import ClientDisconnect
from app.api.routes import speech
from app.schemas.speech import TtsSegmentRequest


def test_single_audio_request_stops_work_after_disconnect():
    async def run():
        closed = []
        async def work():
            try: await asyncio.Event().wait()
            finally: closed.append(True)
        class Request:
            async def is_disconnected(self): return True
        with pytest.raises(asyncio.CancelledError): await speech.until_disconnected(Request(), work())
        assert closed
    asyncio.run(run())


def test_tts_send_failure_closes_all_pending_work(monkeypatch):
    closed = []
    async def stream(*args, **kwargs):
        try:
            yield 0, 'test', b'audio'
            await asyncio.Event().wait()
        finally: closed.append(True)
    monkeypatch.setattr(speech.TtsService, 'synthesize_segments_streaming', stream)
    async def run():
        response = await speech.text_to_speech_stream(TtsSegmentRequest(text='test'))
        async def receive(): return {'type': 'http.disconnect'}
        async def send(message):
            if b'"type": "segment"' in message.get('body', b''): raise OSError('disconnected')
        with pytest.raises(ClientDisconnect):
            await response({'type': 'http', 'asgi': {'spec_version': '2.4'}}, receive, send)
        assert closed
    asyncio.run(run())


def test_tts_wire_ids_and_errors_are_safe(monkeypatch):
    async def broken(*args, **kwargs):
        yield 0, 'test', b'audio'
        raise RuntimeError('private credential or path')
    monkeypatch.setattr(speech.TtsService, 'synthesize_segments_streaming', broken)
    app = FastAPI()
    app.include_router(speech.router)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/speech/tts/stream', json={'text': 'test', 'request_id': 'fixture'})
            assert response.status_code == 200
            assert 'private credential' not in response.text
            assert '"request_id": "fixture"' in response.text
            assert '"segment_id": "0:0"' in response.text
            assert '"type": "error"' in response.text
            assert '"type": "done"' not in response.text
    asyncio.run(run())
