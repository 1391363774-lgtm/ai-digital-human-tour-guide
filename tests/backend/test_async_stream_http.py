import asyncio
from contextlib import aclosing

import httpx
import pytest

from app.services.llm_client import FailoverLLMClient, LLMClientError, OpenAICompatibleLLMClient


class Body(httpx.AsyncByteStream):
    def __init__(self):
        self.waiting = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        yield b': keepalive\n\ndata: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
        self.waiting.set()
        await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


def test_cancellation_closes_real_async_http_response_and_failover_wrapper():
    async def run():
        body = Body()

        async def handler(request):
            return httpx.Response(200, stream=body)

        remote = OpenAICompatibleLLMClient("p", "https://model.invalid/v1", "fake", "fake",
                                           async_transport=httpx.MockTransport(handler))

        async def consume():
            async with aclosing(FailoverLLMClient([remote]).achat_stream([])) as stream:
                async for text in stream:
                    assert text == "hello"

        task = asyncio.create_task(consume())
        await asyncio.wait_for(body.waiting.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert body.closed

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["empty", "whitespace", "timeout", "http500"])
def test_async_http_failure_before_text_tries_backup(failure):
    async def run():
        calls = []

        async def handler(request):
            calls.append(request.url.host)
            if request.url.host == "backup.invalid":
                return httpx.Response(200, content=b'data: {"choices":[{"delta":{"content":"backup"}}]}\n\ndata: [DONE]\n\n')
            if failure == "timeout":
                raise httpx.ReadTimeout("fake timeout")
            if failure == "http500":
                return httpx.Response(500)
            text = "   " if failure == "whitespace" else ""
            import json
            return httpx.Response(200, content=f'data: {json.dumps({"choices": [{"delta": {"content": text}}]})}\n\ndata: [DONE]\n\n'.encode())

        def remote(host):
            return OpenAICompatibleLLMClient(host, f"https://{host}.invalid/v1", "fake", "fake",
                                             async_transport=httpx.MockTransport(handler))

        client = FailoverLLMClient([remote("primary"), remote("backup")])
        assert [text async for text in client.achat_stream([])] == ["backup"]
        assert calls == ["primary.invalid", "backup.invalid"]

    asyncio.run(run())
