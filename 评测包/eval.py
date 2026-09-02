"""
灵山胜境 AI 导游问答准确率评测脚本（独立可移植版）
====================================================

只需一个 Python 3.8+ 环境，无需安装任何第三方库。
支持两种 API 模式：
  1. openai  : OpenAI 兼容接口（/v1/chat/completions）
  2. custom  : 自定义 HTTP 接口（POST 一个 JSON，返回一个 JSON）

用法示例：

  # OpenAI 兼容接口
  python eval.py --mode openai --api-url http://localhost:8000/v1/chat/completions --api-key sk-xxx --model deepseek-chat

  # 自定义接口（默认发送 {"question": "..."}，从 "answer" 字段取回答）
  python eval.py --mode custom --api-url http://localhost:8000/api/chat --question-field question --answer-field answer

  # 只跑前 10 题快速测试
  python eval.py --mode openai --api-url ... --limit 10

  # 指定输出文件
  python eval.py --mode custom --api-url ... --output my_report.json

评测维度：
  - 回答准确率：回答中是否包含期望的关键词
  - 拒答正确率：超范围问题是否正确拒答
  - 分类别统计：factual/intro/cultural/comparative/route/paraphrase/boundary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


# ════════════════════════════════════════════════════════
# 常量
# ════════════════════════════════════════════════════════
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = SCRIPT_DIR / "qa_testset.json"
DEFAULT_OUTPUT = SCRIPT_DIR / "eval_report.json"

PASS_THRESHOLD = 0.6  # 关键词匹配 ≥60% 算通过

# 拒答标志词
REFUSAL_MARKERS = [
    "无法提供", "无法回答", "不能回答", "不能帮", "暂未找到", "暂时没有",
    "超出我的", "超出了我的", "不在我的", "不在讲解范围", "不涉及景区",
    "请咨询景区", "换个景点", "换一个景点",
]

# 系统提示词（OpenAI 模式下发送）
SYSTEM_PROMPT = (
    "你是灵山胜境 AI 数字人导游。请基于景区知识回答游客问题。"
    "如果问题与灵山胜境景区无关，请礼貌拒答并引导回景区话题。"
)


# ════════════════════════════════════════════════════════
# HTTP 请求
# ════════════════════════════════════════════════════════
def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_openai_api(api_url: str, api_key: str, model: str, question: str) -> str:
    """调用 OpenAI 兼容接口，返回回答文本。"""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        "temperature": 0.1,
        "max_tokens": 800,
    }
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = _post_json(api_url, payload, headers=headers)
    try:
        return resp["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return json.dumps(resp, ensure_ascii=False)[:500]


def call_custom_api(api_url: str, question_field: str, answer_field: str,
                    extra_fields: str, question: str) -> str:
    """调用自定义 HTTP 接口，返回回答文本。"""
    payload: dict[str, Any] = {question_field: question}
    if extra_fields:
        for pair in extra_fields.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                payload[k.strip()] = v.strip()
    resp = _post_json(api_url, payload)

    # 支持嵌套路径，如 "data.answer"
    parts = answer_field.split(".")
    val: Any = resp
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part, "")
        else:
            val = ""
            break
    return str(val) if val else json.dumps(resp, ensure_ascii=False)[:500]


# ════════════════════════════════════════════════════════
# 评分逻辑
# ════════════════════════════════════════════════════════
def contains_keyword(answer: str, keyword: str) -> bool:
    """匹配文本关键词；纯数字使用数值边界，避免把 9 错配到 1997。"""
    if not keyword:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", keyword):
        pattern = rf"(?<![\d.]){re.escape(keyword)}(?![\d.])"
        return re.search(pattern, answer) is not None
    return keyword in answer


def score_answer(
    answer: str,
    expected_keywords: list[str],
    expected_keyword_groups: list[list[str]] | None = None,
) -> tuple[float, list[str]]:
    """按关键词组评分；同组词是别名，命中任意一个即算该组通过。"""
    groups = expected_keyword_groups or [[keyword] for keyword in expected_keywords]
    groups = [group for group in groups if any(group)]
    if not groups:
        return 1.0, []

    matched: list[str] = []
    passed_groups = 0
    for group in groups:
        matched_alias = next((word for word in group if contains_keyword(answer, word)), None)
        if matched_alias:
            passed_groups += 1
            matched.append(matched_alias)
    return passed_groups / len(groups), matched


def check_refusal(answer: str) -> bool:
    """检测回答是否为拒答。"""
    return any(marker in answer for marker in REFUSAL_MARKERS)


# ════════════════════════════════════════════════════════
# 评测主流程
# ════════════════════════════════════════════════════════
def run_eval(dataset: list[dict], args: argparse.Namespace) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    total = len(dataset)

    for idx, item in enumerate(dataset):
        qid = item["id"]
        question = item["question"]
        expected_keywords = item.get("expected_keywords", [])
        expected_keyword_groups = item.get("expected_keyword_groups")
        should_refuse = item.get("should_refuse", False)
        category = item.get("category", "")

        # 调用 API
        try:
            if args.mode == "openai":
                answer = call_openai_api(args.api_url, args.api_key, args.model, question)
            else:
                answer = call_custom_api(
                    args.api_url, args.question_field, args.answer_field,
                    args.extra_fields, question,
                )
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                ValueError, OSError, ConnectionError) as exc:
            results.append({
                "id": qid, "question": question, "category": category,
                "answer": "", "error": str(exc),
                "answer_score": 0, "answer_ok": False,
                "refusal_correct": False,
            })
            print(f"  ({idx+1}/{total}) {qid} ERROR: {exc}")
            continue

        # 评分
        if should_refuse:
            # 边界题：检查是否拒答
            is_refusal = check_refusal(answer)
            answer_score = 1.0 if is_refusal else 0.0
            answer_matched: list[str] = []
            answer_ok = is_refusal
        else:
            answer_score, answer_matched = score_answer(
                answer,
                expected_keywords,
                expected_keyword_groups=expected_keyword_groups,
            )
            answer_ok = answer_score >= PASS_THRESHOLD

        refusal_correct = True
        if should_refuse:
            refusal_correct = check_refusal(answer)
        elif check_refusal(answer):
            # 不该拒答却拒答了
            refusal_correct = False

        results.append({
            "id": qid,
            "question": question,
            "category": category,
            "difficulty": item.get("difficulty", ""),
            "answer": answer[:500],
            "answer_score": round(answer_score, 3),
            "answer_matched": answer_matched,
            "answer_ok": answer_ok,
            "should_refuse": should_refuse,
            "refusal_correct": refusal_correct,
        })

        mark = "PASS" if answer_ok else "FAIL"
        if should_refuse:
            mark = "REFUSE-OK" if refusal_correct else "REFUSE-FAIL"
        print(f"  ({idx+1}/{total}) {qid} {mark} score={answer_score:.2f} "
              f"[{category}] {question[:30]}")

    # 统计
    answer_pass = sum(1 for r in results if r["answer_ok"])
    refusal_total = sum(1 for r in results if r.get("should_refuse"))
    refusal_pass = sum(1 for r in results if r.get("should_refuse") and r["refusal_correct"])

    # 分类别统计
    cat_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"total": 0, "pass": 0, "sum_score": 0.0}
    )
    for r in results:
        cat = r["category"]
        cat_stats[cat]["total"] += 1
        if r["answer_ok"]:
            cat_stats[cat]["pass"] += 1
        cat_stats[cat]["sum_score"] += r["answer_score"]

    summary = {
        "total": total,
        "answer_accuracy": round(answer_pass / total, 4) if total else 0,
        "refusal_accuracy": round(refusal_pass / refusal_total, 4) if refusal_total else 1.0,
        "answer_pass": answer_pass,
        "refusal_pass": refusal_pass,
        "refusal_total": refusal_total,
        "avg_answer_score": round(sum(r["answer_score"] for r in results) / total, 4) if total else 0,
        "category_breakdown": {
            cat: {
                "total": v["total"],
                "pass": v["pass"],
                "accuracy": round(v["pass"] / v["total"], 4) if v["total"] else 0,
                "avg_score": round(v["sum_score"] / v["total"], 4) if v["total"] else 0,
            }
            for cat, v in sorted(cat_stats.items())
        },
        "results": results,
    }
    return summary


# ════════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════════
def main() -> None:
    parser = argparse.ArgumentParser(
        description="灵山胜境 AI 导游问答准确率评测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：

  # OpenAI 兼容接口
  python eval.py --mode openai --api-url http://localhost:8000/v1/chat/completions --api-key sk-xxx --model deepseek-chat

  # 自定义接口
  python eval.py --mode custom --api-url http://localhost:8000/api/chat --question-field message --answer-field data.answer

  # 快速测试前 10 题
  python eval.py --mode openai --api-url ... --limit 10
        """,
    )
    parser.add_argument("--mode", choices=["openai", "custom"], default="custom",
                        help="API 模式：openai=OpenAI兼容接口，custom=自定义HTTP接口（默认custom）")
    parser.add_argument("--api-url", required=True, help="API 地址")
    parser.add_argument("--api-key", default="", help="API Key（openai模式用）")
    parser.add_argument("--model", default="deepseek-chat", help="模型名（openai模式用）")
    parser.add_argument("--question-field", default="question",
                        help="请求中问题字段名（custom模式用，默认question）")
    parser.add_argument("--answer-field", default="answer",
                        help="响应中回答字段路径，支持点号嵌套如 data.answer（custom模式用）")
    parser.add_argument("--extra-fields", default="",
                        help="额外请求字段，格式 key=value,key2=value2（custom模式用）")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="评测集路径")
    parser.add_argument("--limit", type=int, default=0, help="只评测前N题，0=全部")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="报告输出路径")
    args = parser.parse_args()

    # 加载数据集
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.limit > 0:
        dataset = dataset[:args.limit]
    print(f"评测集：{args.dataset}（{len(dataset)} 题）")
    print(f"API 模式：{args.mode}")
    print(f"API 地址：{args.api_url}")
    print()

    # 健康检查（第1题测试连接）
    if dataset:
        try:
            if args.mode == "openai":
                test = call_openai_api(args.api_url, args.api_key, args.model, "你好")
            else:
                test = call_custom_api(
                    args.api_url, args.question_field, args.answer_field,
                    args.extra_fields, "你好",
                )
            print(f"连接测试：通过（返回 {len(test)} 字符）\n")
        except Exception as exc:
            print(f"连接测试失败：{exc}")
            print("请检查 API 地址和参数。")
            sys.exit(1)

    # 运行评测
    started = time.perf_counter()
    summary = run_eval(dataset, args)
    elapsed = time.perf_counter() - started
    summary["elapsed_seconds"] = round(elapsed, 1)

    # 保存报告
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_size": len(dataset),
        "api_mode": args.mode,
        "api_url": args.api_url,
        "summary": summary,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印结果
    print(f"\n{'='*60}")
    print("评测结果")
    print(f"{'='*60}")
    print(f"  回答准确率：{summary['answer_accuracy']:.2%} ({summary['answer_pass']}/{summary['total']})")
    print(f"  拒答正确率：{summary['refusal_accuracy']:.2%} ({summary['refusal_pass']}/{summary['refusal_total']})")
    print(f"  平均回答得分：{summary['avg_answer_score']:.4f}")
    print(f"  耗时：{elapsed:.1f}s")

    print(f"\n{'='*60}")
    print("分类别准确率")
    print(f"{'='*60}")
    print(f"{'类别':<14} {'题数':>4} {'通过':>4} {'准确率':>8} {'均分':>8}")
    print("-" * 60)
    for cat, v in sorted(summary["category_breakdown"].items()):
        print(f"{cat:<14} {v['total']:>4} {v['pass']:>4} {v['accuracy']:>7.1%} {v['avg_score']:>8.4f}")

    print(f"\n报告已保存：{args.output}")


if __name__ == "__main__":
    main()
