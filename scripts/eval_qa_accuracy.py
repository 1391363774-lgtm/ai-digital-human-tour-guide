"""问答准确率评测脚本。

用法：
    python scripts/eval_qa_accuracy.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "eval" / "qa_testset.json"


def request_answer(base_url: str, question: str) -> str:
    payload = json.dumps({"message": question, "top_k": 5}, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat/messages",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("data", {}).get("answer", ""))


def score_answer(answer: str, expected_keywords: list[str]) -> tuple[float, list[str]]:
    if not expected_keywords:
        return 1.0, []
    matched = [keyword for keyword in expected_keywords if keyword and keyword in answer]
    return len(matched) / len(expected_keywords), matched


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> None:
    parser = argparse.ArgumentParser(description="景区导览服务问答准确率评测")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="评测集 JSON 路径")
    parser.add_argument("--limit", type=int, default=0, help="只评测前 N 条，0 表示全部")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if args.limit > 0:
        dataset = dataset[: args.limit]

    results: list[dict[str, Any]] = []
    for item in dataset:
        question = item["question"]
        expected_keywords = item.get("expected_keywords", [])
        try:
            answer = request_answer(args.base_url, question)
            score, matched = score_answer(answer, expected_keywords)
            ok = score >= 0.6
            results.append({**item, "score": score, "matched_keywords": matched, "ok": ok})
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {item['id']} score={score:.2f} matched={matched}")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            results.append({**item, "score": 0, "matched_keywords": [], "ok": False, "error": str(exc)})
            print(f"[FAIL] {item['id']} error={exc}")

    passed = sum(1 for item in results if item["ok"])
    total = len(results)
    accuracy = passed / total if total else 0
    print(f"\n准确率：{accuracy:.2%}（{passed}/{total}）")
    if accuracy < 0.8:
        sys.exit(1)


if __name__ == "__main__":
    main()
