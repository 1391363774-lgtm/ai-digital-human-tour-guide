from pathlib import Path
import asyncio
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm_client import (  # noqa: E402
    BaseLLMClient,
    ChatMessage,
    FailoverLLMClient,
    LLMClientError,
    LLMResponse,
)


class StubClient(BaseLLMClient):
    def __init__(self, provider: str, chunks=None, error: str | None = None) -> None:
        self.provider = provider
        self.model = f"{provider}-model"
        self.chunks = chunks or []
        self.error = error
        self.stream_calls = 0
        self.closed = 0

    def chat(self, messages, temperature=0.1):
        if self.error:
            raise LLMClientError(self.error)
        return LLMResponse("".join(self.chunks), self.provider, self.model)

    def chat_stream(self, messages, temperature=0.1):
        self.stream_calls += 1
        try:
            for chunk in self.chunks:
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
            if self.error:
                raise LLMClientError(self.error)
        finally:
            self.closed += 1

    async def achat_stream(self, messages, temperature=0.1):
        stream = self.chat_stream(messages, temperature)
        try:
            for chunk in stream:
                yield chunk
        finally:
            stream.close()


MESSAGES = [ChatMessage(role="user", content="请介绍灵山大佛")]


def test_non_streaming_falls_back_to_second_client():
    client = FailoverLLMClient([
        StubClient("primary", error="unavailable"),
        StubClient("secondary", chunks=["可靠回答"]),
    ])

    response = client.chat(MESSAGES)

    assert response.provider == "secondary"
    assert response.content == "可靠回答"


def test_streaming_falls_back_before_first_token():
    client = FailoverLLMClient([
        StubClient("primary", error="unavailable"),
        StubClient("secondary", chunks=["第二", "模型"]),
    ])

    assert list(client.chat_stream(MESSAGES)) == ["第二", "模型"]


def test_streaming_does_not_mix_models_after_output_started():
    client = FailoverLLMClient([
        StubClient("primary", chunks=["已经输出", LLMClientError("late failure")]),
        StubClient("secondary", chunks=["不应拼接"]),
    ])

    stream = client.chat_stream(MESSAGES)
    assert next(stream) == "已经输出"
    try:
        next(stream)
    except LLMClientError as exc:
        assert "late failure" in str(exc)
    else:
        raise AssertionError("流式输出开始后不应静默切换模型")


def collect(client, mode):
    if mode == "sync":
        return list(client.chat_stream(MESSAGES))

    async def run():
        return [chunk async for chunk in client.achat_stream(MESSAGES)]

    return asyncio.run(run())


@pytest.mark.parametrize("mode", ["sync", "async"])
@pytest.mark.parametrize("chunks", [[], [""], [" ", "\n", "\t"], [" ", LLMClientError("early")]])
def test_no_effective_text_uses_secondary(mode, chunks):
    primary = StubClient("primary", chunks)
    secondary = StubClient("secondary", ["备用", "成功"])
    assert collect(FailoverLLMClient([primary, secondary]), mode) == ["备用", "成功"]
    assert primary.closed == secondary.closed == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_partial_failure_never_calls_secondary(mode):
    primary = StubClient("primary", ["第一段", LLMClientError("late")])
    secondary = StubClient("secondary", ["另一模型"])
    with pytest.raises(LLMClientError, match="late"):
        collect(FailoverLLMClient([primary, secondary]), mode)
    assert secondary.stream_calls == 0
    assert primary.closed == 1


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_all_empty_clients_raise(mode):
    with pytest.raises(LLMClientError, match="有效文本"):
        collect(FailoverLLMClient([StubClient("p"), StubClient("s", [" "])]), mode)


@pytest.mark.parametrize("content", ["", "  \n"])
def test_non_streaming_empty_response_uses_secondary(content):
    response = FailoverLLMClient([StubClient("p", [content]), StubClient("s", ["成功"])]).chat(MESSAGES)
    assert response.provider == "s"


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_whitespace_after_effective_output_is_preserved(mode):
    primary = StubClient("p", [" ", "hello", " ", "world"])
    secondary = StubClient("s", ["not called"])
    assert collect(FailoverLLMClient([primary, secondary]), mode) == ["hello", " ", "world"]
    assert secondary.stream_calls == 0
