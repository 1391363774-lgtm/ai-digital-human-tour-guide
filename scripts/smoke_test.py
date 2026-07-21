"""MVP HTTP 冒烟测试。

用法：
    python scripts/smoke_test.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def run_check(name: str, func) -> CheckResult:
    started = time.perf_counter()
    try:
        data = func()
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CheckResult(name=name, ok=True, detail=f"{elapsed_ms}ms | {summarize(data)}")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        return CheckResult(name=name, ok=False, detail=str(exc))


def summarize(data: Any) -> str:
    if isinstance(data, dict):
        if "code" in data and "data" in data:
            payload = data["data"]
            if isinstance(payload, dict):
                return ", ".join(f"{key}={short(value)}" for key, value in list(payload.items())[:4])
            return short(payload)
        return ", ".join(f"{key}={short(value)}" for key, value in list(data.items())[:4])
    return short(data)


def short(value: Any) -> str:
    text = str(value)
    return text if len(text) <= 80 else text[:77] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="景区导览服务 AI 数字人 MVP 冒烟测试")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    args = parser.parse_args()

    checks = [
        run_check("health", lambda: request_json(args.base_url, "GET", "/health")),
        run_check("scenic spots", lambda: request_json(args.base_url, "GET", "/api/spots")),
        run_check(
            "chat fallback",
            lambda: request_json(
                args.base_url,
                "POST",
                "/api/chat/messages",
                {"message": "请用一句话介绍灵山大佛"},
            ),
        ),
        run_check(
            "route recommend",
            lambda: request_json(
                args.base_url,
                "POST",
                "/api/routes/recommend",
                {"interest": "历史文化", "duration_hours": 3, "group_type": "普通游客"},
            ),
        ),
        run_check("feedback stats", lambda: request_json(args.base_url, "GET", "/api/feedback/stats")),
        run_check("dashboard overview", lambda: request_json(args.base_url, "GET", "/api/dashboard/overview")),
    ]

    for result in checks:
        mark = "PASS" if result.ok else "FAIL"
        print(f"[{mark}] {result.name}: {result.detail}")

    failed = [result for result in checks if not result.ok]
    if failed:
        print(f"\n冒烟测试未通过：{len(failed)} 项失败。", file=sys.stderr)
        return 1
    print("\n冒烟测试通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
