"""Real loopback HTTP probe; no model, database, Chroma or TTS is contacted."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = ""
os.environ["QWEN_API_KEY"] = ""


def serve(port: int, trace: Path) -> None:
    import httpx
    import uvicorn
    from fastapi import FastAPI
    from app.api.routes import chat

    def record(event, label=""):
        with trace.open("a", encoding="utf-8") as output:
            output.write(json.dumps({"event": event, "label": label, "at": time.time()}) + "\n")

    class Service:
        def __init__(self, db):
            pass

        def prepare_stream(self, question, *args):
            record("prepare", question)
            return SimpleNamespace(id=question), [SimpleNamespace(content=question)], [], None, None

        def persist_stream_answer(self, *args, **kwargs):
            record("persist", args[0].id)

    class SlowBody(httpx.AsyncByteStream):
        def __init__(self, label):
            self.label = label

        async def __aiter__(self):
            record("upstream_open", self.label)
            for index in range(10):
                await asyncio.sleep(0.15)
                record("upstream_chunk", self.label)
                yield f'data: {{"choices":[{{"delta":{{"content":"{index}"}}}}]}}\n\n'.encode()

        async def aclose(self):
            record("upstream_close", self.label)

    class SlowClient:
        # The original route uses this blocking iterator.
        def chat_stream(self, messages):
            label = messages[0].content
            record("upstream_open", label)
            try:
                for index in range(10):
                    time.sleep(0.15)
                    record("upstream_chunk", label)
                    yield str(index)
            finally:
                record("upstream_close", label)

        # The fixed route uses the actual async HTTP parser with a fake body.
        def achat_stream(self, messages):
            from app.services.llm_client import OpenAICompatibleLLMClient
            label = messages[0].content

            async def handler(request):
                return httpx.Response(200, stream=SlowBody(label))

            return OpenAICompatibleLLMClient(
                "probe", "https://model.invalid/v1", "test-only", "fake",
                async_transport=httpx.MockTransport(handler),
            ).achat_stream([])

    chat.ChatService = Service
    chat.get_llm_client = SlowClient
    app = FastAPI()
    app.dependency_overrides[chat.get_db] = lambda: object()
    app.include_router(chat.router)

    @app.get("/health")
    async def health():
        record("health")
        return {"status": "ok"}

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


async def probe(base_url: str, trace: Path) -> dict:
    import httpx
    timeline = []
    started = time.time()

    def mark(event):
        timeline.append({"event": event, "ms": round((time.time() - started) * 1000, 2)})

    async with httpx.AsyncClient(base_url=base_url, trust_env=False, timeout=12) as client:
        async def stream(label, cancel=False):
            mark(f"{label}_request")
            async with client.stream("POST", "/api/chat/stream", json={"message": label}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    mark(f"{label}_{event['type']}")
                    if cancel and event["type"] == "text":
                        mark("A_cancel_requested")
                        break
            mark(f"{label}_client_closed")

        async def health():
            mark("health_request")
            response = await client.get("/health")
            response.raise_for_status()
            mark("health_response")

        a = asyncio.create_task(stream("A", cancel=True))
        # Observe the producer, not a possibly buffered client event. This also
        # measures the original route while its event loop is actually blocked.
        for _ in range(500):
            if '"upstream_open"' in trace.read_text(encoding="utf-8"):
                break
            await asyncio.sleep(0.01)
        else:
            raise RuntimeError("first model stream did not start")
        await asyncio.gather(a, health(), stream("B"))
        await asyncio.sleep(0.2)

    server = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    for event in server:
        event["ms"] = round((event.pop("at") - started) * 1000, 2)
    at = {item["event"]: item["ms"] for item in timeline if item["event"] != "B_text"}
    closed = next(item["ms"] for item in server if item["event"] == "upstream_close" and item["label"] == "A")
    b_first = next(item["ms"] for item in timeline if item["event"] == "B_text")
    metrics = {
        "health_latency_ms": round(at["health_response"] - at["health_request"], 2),
        "second_stream_first_text_ms": round(b_first - at["B_request"], 2),
        "cancel_to_upstream_close_ms": round(closed - at["A_cancel_requested"], 2),
        "cancelled_stream_chunks": sum(e["event"] == "upstream_chunk" and e["label"] == "A" for e in server),
        "both_upstreams_closed": sum(e["event"] == "upstream_close" for e in server) == 2,
    }
    return {"scenario": "two 10x150ms fake model streams, cancel A after first text", "metrics": metrics,
            "client_timeline": timeline, "server_timeline": server}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", type=int)
    parser.add_argument("--trace", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--assert-responsive", action="store_true")
    args = parser.parse_args()
    if args.serve:
        serve(args.serve, args.trace)
        return

    with tempfile.TemporaryDirectory(prefix="sse-probe-") as folder:
        trace = Path(folder) / "trace.jsonl"
        trace.touch()
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen([sys.executable, __file__, "--serve", str(port), "--trace", str(trace)], cwd=ROOT)
        try:
            import httpx
            with httpx.Client(trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("probe server exited")
                    try:
                        client.get(f"http://127.0.0.1:{port}/health").raise_for_status()
                        break
                    except httpx.TransportError:
                        time.sleep(0.05)
                else:
                    raise RuntimeError("probe server did not start")
            report = asyncio.run(probe(f"http://127.0.0.1:{port}", trace))
        finally:
            process.terminate()
            process.wait(timeout=10)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False))
    if args.assert_responsive:
        metrics = report["metrics"]
        assert metrics["health_latency_ms"] < 750, metrics
        assert metrics["second_stream_first_text_ms"] < 1000, metrics
        assert metrics["cancelled_stream_chunks"] < 10, metrics
        assert metrics["cancel_to_upstream_close_ms"] < 750, metrics
        assert metrics["both_upstreams_closed"], metrics


if __name__ == "__main__":
    main()
