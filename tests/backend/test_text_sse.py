import asyncio
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from app.api.routes import chat
from app.schemas.chat import ChatMessageRequest
from app.services.llm_client import LLMClientError


@pytest.mark.parametrize("mode", ["normal", "partial_error", "early_error", "refusal", "fast"])
def test_sse_protocol_and_database_work_stays_off_event_loop(monkeypatch, mode):
    main_thread = threading.get_ident()
    saved = []

    class Service:
        def __init__(self, db):
            pass

        def prepare_stream(self, *args):
            assert threading.get_ident() != main_thread
            return SimpleNamespace(id=1), [], [], "refused" if mode == "refusal" else None, "fast" if mode == "fast" else None

        def persist_stream_answer(self, conversation, answer, *args, **kwargs):
            assert threading.get_ident() != main_thread
            saved.append(answer)

    class Client:
        async def achat_stream(self, messages):
            assert mode not in ("refusal", "fast")
            if mode != "early_error":
                yield "first"
            if "error" in mode:
                raise LLMClientError("failure")

    monkeypatch.setattr(chat, "ChatService", Service)
    monkeypatch.setattr(chat, "get_llm_client", Client)

    async def run():
        response = await chat.chat_stream(ChatMessageRequest(message="test"), db=object())
        return [event async for event in response.body_iterator]

    events = asyncio.run(run())
    assert '"type": "done"' in events[-1]
    if mode in ("fast", "refusal"):
        expected = "local_fast_rag" if mode == "fast" else "rule"
        assert f'"provider": "{expected}"' in events[-1]
    assert any('"type": "error"' in event for event in events) == ("error" in mode)
    assert saved == [{"refusal": "refused", "early_error": "", "fast": "fast"}.get(mode, "first")]


def test_real_http_streams_progress_and_cancel(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "scripts/probe_sse_concurrency.py"), "--assert-responsive",
         "--output", str(tmp_path / "sse.json")], cwd=root, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_asgi24_send_failure_closes_generator_immediately(monkeypatch):
    from starlette.requests import ClientDisconnect
    closed = []

    class Service:
        def __init__(self, db):
            pass

        def prepare_stream(self, *args):
            return SimpleNamespace(id=1), [], [], None, None

        def persist_stream_answer(self, *args, **kwargs):
            assert kwargs['status'] == 'cancelled'

    class Client:
        async def achat_stream(self, messages):
            try:
                yield "first"
                await asyncio.Event().wait()
            finally:
                closed.append(True)

    monkeypatch.setattr(chat, "ChatService", Service)
    monkeypatch.setattr(chat, "get_llm_client", Client)

    async def run():
        response = await chat.chat_stream(ChatMessageRequest(message="test"), db=object())

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            if b'"type": "text"' in message.get("body", b""):
                raise OSError("client socket closed")

        with pytest.raises(ClientDisconnect):
            await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)
        assert closed, "upstream must close before this response returns, not at GC time"

    asyncio.run(run())
