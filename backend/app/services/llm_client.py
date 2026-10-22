from __future__ import annotations

import json
import urllib.error
import urllib.request
import urllib.parse
import http.client
import ssl
import logging
from contextlib import aclosing, closing
from dataclasses import dataclass

import httpx
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str
    # Internal provenance, never derived from the visitor's text or sent to providers.
    reference_data: bool = False


@dataclass(frozen=True)
class LLMResponse:
    content: str
    provider: str
    model: str
    raw: dict | None = None


class LLMClientError(RuntimeError):
    pass


class BaseLLMClient:
    provider: str
    model: str

    def chat(self, messages: list[ChatMessage], temperature: float = 0.1) -> LLMResponse:
        raise NotImplementedError

    def chat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        """默认将非流式客户端适配为单段流。

        云端客户端可覆盖此方法提供真正的 token 流；本地兜底则直接输出完整回答。
        """
        yield self.chat(messages, temperature=temperature).content

    async def achat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        """Local/non-streaming implementations run outside the event loop."""
        response = await run_in_threadpool(self.chat, messages, temperature)
        yield response.content


class OpenAICompatibleLLMClient(BaseLLMClient):
    def __init__(self, provider: str, base_url: str, api_key: str, model: str, *,
                 async_transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.async_transport = async_transport

    async def achat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        """Async socket reads allow other requests and disconnect cancellation."""
        payload = {
            "model": self.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": temperature, "max_tokens": 800, "stream": True,
        }
        try:
            settings = get_settings()
            finished = False
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.llm_read_timeout, connect=settings.llm_connect_timeout), transport=self.async_transport,
            ) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions", json=payload,
                    headers={"Authorization": f"Bearer {self.api_key}", "Accept": "text/event-stream"},
                ) as response:
                    if response.status_code >= 400:
                        raise LLMClientError(f"{self.provider} 调用失败：HTTP {response.status_code}")
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data:
                            continue
                        if data == "[DONE]":
                            return
                        try:
                            parsed = json.loads(data)
                            if not parsed.get("choices") and "usage" in parsed:
                                continue
                            choice = parsed["choices"][0]
                            content = choice["delta"].get("content")
                            reason = choice.get("finish_reason")
                            if reason and reason != "stop":
                                raise LLMClientError("模型输出未完整结束")
                            finished = finished or reason == "stop"
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError, AttributeError) as exc:
                            raise LLMClientError("模型流协议无效") from exc
                        if isinstance(content, str) and content:
                            yield content
                    if not finished:
                        raise LLMClientError("模型连接提前关闭，缺少结束标记")
        except httpx.HTTPError as exc:
            raise LLMClientError(f"{self.provider} 网络不可用：{type(exc).__name__}") from exc

    def chat(self, messages: list[ChatMessage], temperature: float = 0.1) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": temperature,
            "max_tokens": 800,
            "stream": False,
        }
        return self._request(payload)

    def chat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        """流式返回，用底层 socket 逐行读取，避免 urllib 全量缓冲。"""
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
            "temperature": temperature,
            "max_tokens": 800,
            "stream": True,
        }, ensure_ascii=False).encode("utf-8")

        parsed = urllib.parse.urlparse(self.base_url)
        host = parsed.hostname
        port = parsed.port or 443
        path = parsed.path.rstrip("/") + "/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, port, context=ctx, timeout=60)
        try:
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()

            if response.status >= 400:
                detail = response.read().decode("utf-8", errors="ignore")
                raise LLMClientError(f"{self.provider} 调用失败：HTTP {response.status} {detail}")

            # 逐行读取——不缓冲，真正的流式
            while True:
                line = response.readline()
                if not line:
                    break
                line = line.decode("utf-8").strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    return
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
        except (http.client.HTTPException, OSError) as exc:
            raise LLMClientError(f"{self.provider} 网络不可用：{exc}") from exc
        finally:
            conn.close()

    def _request(self, payload: dict) -> LLMResponse:
        """非流式请求。"""
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise LLMClientError(f"{self.provider} 调用失败：HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise LLMClientError(f"{self.provider} 网络不可用：{exc.reason}") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"{self.provider} 返回格式异常") from exc
        return LLMResponse(content=content, provider=self.provider, model=self.model, raw=data)


class LocalFallbackLLMClient(BaseLLMClient):
    provider = "local_fallback"
    model = "template-guide"

    def chat(self, messages: list[ChatMessage], temperature: float = 0.1) -> LLMResponse:
        user_message = next((item.content for item in reversed(messages) if item.role == "user"), "")
        context = ""
        for item in messages:
            if item.reference_data and item.content.startswith("REFERENCE_DATA_JSON\n"):
                try:
                    evidence = json.loads(item.content.split("\n", 1)[1])["evidence"]
                    context = "\n\n".join(f"[{record['label']}] {record['content']}" for record in evidence)
                except (ValueError, KeyError, TypeError):
                    context = ""
        content = build_local_answer(user_message, context)
        return LLMResponse(content=content, provider=self.provider, model=self.model)


class FailoverLLMClient(BaseLLMClient):
    """按配置顺序尝试模型，并始终以本地知识库回答收尾。

    流式调用只有在尚未输出有效文本时才会切换到下一模型，避免把两个模型的
    半段回答拼在一起。这一约束也让故障行为更容易复现和解释。
    """

    provider = "failover"

    def __init__(self, clients: list[BaseLLMClient]) -> None:
        if not clients:
            raise ValueError("failover 至少需要一个客户端")
        self.clients = clients
        self.model = " -> ".join(client.model for client in clients)
        self.selected_provider = None
        self.selected_model = None
        self.failed_providers: list[str] = []

    def chat(self, messages: list[ChatMessage], temperature: float = 0.1) -> LLMResponse:
        errors: list[str] = []
        for client in self.clients:
            try:
                response = client.chat(messages, temperature=temperature)
                if not isinstance(response.content, str) or not response.content.strip():
                    raise LLMClientError(f"{client.provider} 未返回有效文本")
                return response
            except LLMClientError as exc:
                errors.append(f"{client.provider}: {exc}")
        raise LLMClientError("；".join(errors) or "没有可用的语言模型")

    def chat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        errors: list[str] = []
        for client in self.clients:
            emitted = False
            try:
                with closing(client.chat_stream(messages, temperature=temperature)) as stream:
                    for chunk in stream:
                        if not isinstance(chunk, str) or (not emitted and not chunk.strip()):
                            continue
                        emitted = True
                        yield chunk
                if not emitted:
                    raise LLMClientError(f"{client.provider} 未返回有效文本")
                return
            except LLMClientError as exc:
                if emitted:
                    raise
                errors.append(f"{client.provider}: {exc}")
        raise LLMClientError("；".join(errors) or "没有可用的语言模型")

    async def achat_stream(self, messages: list[ChatMessage], temperature: float = 0.1):
        errors: list[str] = []
        for client in self.clients:
            emitted = False
            try:
                async with aclosing(client.achat_stream(messages, temperature=temperature)) as stream:
                    async for chunk in stream:
                        if not isinstance(chunk, str) or (not emitted and not chunk.strip()):
                            continue
                        emitted = True
                        self.selected_provider = client.provider
                        self.selected_model = client.model
                        yield chunk
                if not emitted:
                    raise LLMClientError(f"{client.provider} 未返回有效文本")
                return
            except LLMClientError as exc:
                logger.warning("model_stream_failed provider=%s emitted=%s", client.provider, emitted)
                self.failed_providers.append(client.provider)
                if emitted:
                    raise
                errors.append(f"{client.provider}: {exc}")
        raise LLMClientError("；".join(errors) or "没有可用的语言模型")


def get_llm_client() -> BaseLLMClient:
    settings = get_settings()
    if settings.demo_mode:
        from app.services.demo_service import DemoLLMClient
        return FailoverLLMClient([DemoLLMClient(), LocalFallbackLLMClient()])
    provider = settings.llm_provider.lower()

    deepseek_client = None
    if settings.deepseek_api_key:
        deepseek_client = OpenAICompatibleLLMClient(
            provider="deepseek",
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
        )

    qwen_client = None
    if settings.qwen_api_key and settings.qwen_base_url:
        qwen_client = OpenAICompatibleLLMClient(
            provider="qwen",
            base_url=settings.qwen_base_url,
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
        )

    cloud_clients: list[BaseLLMClient] = []
    if provider == "qwen":
        cloud_clients = [client for client in (qwen_client, deepseek_client) if client]
    else:
        # deepseek 与 auto 都以 DeepSeek 为首选；若只配置了 Qwen，则直接使用 Qwen。
        cloud_clients = [client for client in (deepseek_client, qwen_client) if client]

    clients = [*cloud_clients, LocalFallbackLLMClient()]
    return clients[0] if len(clients) == 1 else FailoverLLMClient(clients)


def build_local_answer(user_message: str, context: str) -> str:
    if "暂未找到" in context:
        return "我暂时没有在景区知识库中找到可靠依据，建议换个问法或咨询景区工作人员。"
    trimmed_context = context.strip()
    if trimmed_context:
        first_block = trimmed_context.split("\n\n", 1)[0]
        return "当前为本地资料摘录（未使用云模型）：\n" + first_block.strip()[:700]
    return (
        f"你问的是“{user_message}”。当前还没有可用的知识库上下文，"
        "我不能编造景区事实，请先完成知识库入库和索引。"
    )
