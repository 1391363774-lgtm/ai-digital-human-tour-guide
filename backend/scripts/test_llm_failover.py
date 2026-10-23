"""离线故障注入测试：无需 API Key、无需网络。"""
import asyncio
import logging

import httpx

from app.services.llm_service import LlmService, ProviderConfig


def mock_client_factory(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.host)
        if request.url.host == "primary.test":
            return httpx.Response(503, request=request, json={"error": "primary unavailable"})
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "text/event-stream"},
            content=(
                'data: {"choices":[{"delta":{"content":"[emotion:happy]备用模型回答成功。"}}]}\n\n'
                "data: [DONE]\n\n"
            ).encode("utf-8"),
        )

    return lambda timeout: httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=timeout)


async def assert_http_error_failover() -> None:
    calls = []
    service = LlmService(
        primary=ProviderConfig("primary", "https://primary.test", "primary-key", "primary-model", 1),
        fallback=ProviderConfig("fallback", "https://fallback.test", "fallback-key", "fallback-model", 1),
        client_factory=mock_client_factory(calls),
    )
    answer = "".join([token async for token in service.stream_chat("测试", [])])
    assert answer == "[emotion:happy]备用模型回答成功。"
    assert calls == ["primary.test", "fallback.test"]
    print("PASS http_503: primary -> fallback")


async def assert_timeout_failover() -> None:
    calls = []

    def inject_primary_timeout(provider: str):
        return httpx.ReadTimeout("simulated timeout") if provider == "primary" else None

    service = LlmService(
        primary=ProviderConfig("primary", "https://primary.test", "primary-key", "primary-model", 1),
        fallback=ProviderConfig("fallback", "https://fallback.test", "fallback-key", "fallback-model", 1),
        client_factory=mock_client_factory(calls),
        fault_injector=inject_primary_timeout,
    )
    answer = "".join([token async for token in service.stream_chat("测试", [])])
    assert answer == "[emotion:happy]备用模型回答成功。"
    assert calls == ["fallback.test"]
    print("PASS timeout: injected primary timeout -> fallback")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    await assert_http_error_failover()
    await assert_timeout_failover()
    print("ALL PASS: LLM primary/fallback failover works without network access")


if __name__ == "__main__":
    asyncio.run(main())
