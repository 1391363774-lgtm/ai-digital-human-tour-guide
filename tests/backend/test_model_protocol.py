import asyncio
import httpx
import pytest
from app.services.llm_client import OpenAICompatibleLLMClient, LLMClientError


@pytest.mark.parametrize('tail', ['', 'data: invalid\n\n', 'data: {"choices":[{"delta":{},"finish_reason":"length"}]}\n\n'])
def test_partial_or_malformed_model_stream_is_not_completed(tail):
    async def run():
        async def handler(request):
            return httpx.Response(200, content=('data: {"choices":[{"delta":{"content":"partial"}}]}\n\n' + tail).encode())
        client = OpenAICompatibleLLMClient('fake', 'https://fake.invalid', 'test', 'fake', async_transport=httpx.MockTransport(handler))
        stream = client.achat_stream([])
        assert await anext(stream) == 'partial'
        with pytest.raises(LLMClientError): await anext(stream)
    asyncio.run(run())
