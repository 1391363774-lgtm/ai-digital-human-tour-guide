"""端到端延迟评测脚本。

用法：
    python scripts/benchmark_latency.py --base-url http://localhost:8000 --runs 20
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request


QUESTIONS = [
    "请介绍灵山大佛",
    "九龙灌浴有什么看点",
    "我想游览三小时，推荐一条历史文化路线",
    "拈花湾适合晚上游玩吗",
]


def post_chat(base_url: str, question: str) -> None:
    payload = json.dumps({"message": question, "top_k": 5}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat/messages",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        response.read()


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percent)))
    return ordered[index]

def main() -> None:
    parser = argparse.ArgumentParser(description="景区导览服务端到端延迟评测")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--runs", type=int, default=20, help="请求次数")
    args = parser.parse_args()

    latencies: list[float] = []
    for index in range(args.runs):
        question = QUESTIONS[index % len(QUESTIONS)]
        started = time.perf_counter()
        post_chat(args.base_url, question)
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies.append(elapsed_ms)
        print(f"{index + 1:02d}/{args.runs} {elapsed_ms:.0f}ms | {question}")

    print("\n延迟统计")
    print(f"平均：{statistics.mean(latencies):.0f}ms")
    print(f"P50：{percentile(latencies, 0.50):.0f}ms")
    print(f"P95：{percentile(latencies, 0.95):.0f}ms")
    print(f"最大：{max(latencies):.0f}ms")


if __name__ == "__main__":
    main()
