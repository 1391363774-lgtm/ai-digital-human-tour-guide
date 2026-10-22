import asyncio
import json
from types import SimpleNamespace

import pytest

from app.api.routes import chat
from app.schemas.chat import ChatMessageRequest
from app.services.llm_client import LLMClientError


@pytest.mark.parametrize('mode,status', [('normal', 'completed'), ('partial', 'partial'), ('early', 'failed'), ('refused', 'refused'), ('cancel', 'cancelled')])
def test_stream_terminal_status_request_id_and_safe_errors(monkeypatch, mode, status):
    saved = []
    class Service:
        def __init__(self, db): pass
        def prepare_stream(self, *args):
            return SimpleNamespace(id=1), [], [], 'no evidence' if mode == 'refused' else None, None
        def persist_stream_answer(self, conversation, text, *args, **kwargs):
            saved.append((text, kwargs))
    class Client:
        async def achat_stream(self, messages):
            if mode != 'early': yield '部分'
            if mode in ('early', 'partial'): raise LLMClientError('secret-provider-detail')
    monkeypatch.setattr(chat, 'ChatService', Service)
    monkeypatch.setattr(chat, 'get_llm_client', Client)
    async def run():
        response = await chat.chat_stream(ChatMessageRequest(message='test'), db=object())
        events = []
        async for wire in response.body_iterator:
            event = json.loads(wire.removeprefix('data: '))
            events.append(event)
            if mode == 'cancel' and event['type'] == 'text':
                await response.body_iterator.aclose()
                break
        return events
    events = asyncio.run(run())
    assert saved and saved[-1][1]['status'] == status
    assert all(event.get('request_id') == events[0]['request_id'] for event in events)
    assert len(events[0]['request_id']) == 32
    assert 'secret-provider-detail' not in json.dumps(events)
    if mode != 'cancel':
        assert events[-1]['type'] == 'done'
        assert events[-1]['status'] == status
        assert any(event['type'] == 'source' for event in events)
