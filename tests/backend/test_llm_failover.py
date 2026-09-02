from pathlib import Path
import sys


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

    def chat(self, messages, temperature=0.1):
        if self.error:
            raise LLMClientError(self.error)
        return LLMResponse("".join(self.chunks), self.provider, self.model)

    def chat_stream(self, messages, temperature=0.1):
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk
        if self.error:
            raise LLMClientError(self.error)


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
