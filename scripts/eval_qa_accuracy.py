"""问答准确率多模式对比评测脚本。

同时测量检索精度和回答精度，对比以下 4 种做法：
  1. fast_topk5  : fast=true,  top_k=5  （本地抽取式回答）
  2. llm_topk3   : fast=false, top_k=3  （LLM + 少量检索块）
  3. llm_topk5   : fast=false, top_k=5  （LLM + 默认检索块）
  4. llm_topk8   : fast=false, top_k=8  （LLM + 更多检索块）

用法：
    # 全量评测（约 5-10 分钟）
    python scripts/eval_qa_accuracy.py --base-url http://localhost:8000

    # 快速测试前 10 题
    python scripts/eval_qa_accuracy.py --limit 10

    # 只跑指定配置
    python scripts/eval_qa_accuracy.py --configs fast_topk5,llm_topk5

    # 跳过检索评测（只评回答精度）
    python scripts/eval_qa_accuracy.py --skip-retrieval

输出：
    data/eval/eval_report.json  （详细逐题结果）
    终端打印对比汇总表
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "eval" / "qa_testset.json"
REPORT_PATH = PROJECT_ROOT / "data" / "eval" / "eval_report_optimized.json"

# 关键词匹配通过阈值
PASS_THRESHOLD = 0.6

# ──────────────────────────────────────────────
# 评测配置
# ──────────────────────────────────────────────
ALL_CONFIGS: list[dict[str, Any]] = [
    {"name": "fast_topk5", "fast": True,  "top_k": 5},
    {"name": "llm_topk3",  "fast": False, "top_k": 3},
    {"name": "llm_topk5",  "fast": False, "top_k": 5},
    {"name": "llm_topk8",  "fast": False, "top_k": 8},
]


# ──────────────────────────────────────────────
# HTTP 请求
# ──────────────────────────────────────────────
def _post_json(base_url: str, path: str, payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + path,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def request_chat(base_url: str, question: str, fast: bool, top_k: int) -> dict[str, Any]:
    """调用 /api/chat/messages，返回 answer/sources/refused。"""
    raw = _post_json(base_url, "/api/chat/messages", {
        "message": question,
        "top_k": top_k,
        "fast": fast,
    })
    data = raw.get("data", {})
    return {
        "answer": str(data.get("answer", "")),
        "refused": bool(data.get("refused", False)),
        "provider": str(data.get("provider", "")),
        "sources": [
            {"content": s.get("content", ""), "score": s.get("score", 0), "metadata": s.get("metadata", {})}
            for s in data.get("sources", [])
        ],
    }


def request_rag_search(base_url: str, query: str, top_k: int) -> list[dict]:
    """调用 /api/rag/search，返回 hits 列表。"""
    raw = _post_json(base_url, "/api/rag/search", {"query": query, "top_k": top_k})
    data = raw.get("data", {})
    return [
        {"content": h.get("content", ""), "score": h.get("score", 0), "source": h.get("source", {})}
        for h in data.get("hits", [])
    ]


# ──────────────────────────────────────────────
# 评分逻辑
# ──────────────────────────────────────────────
def contains_keyword(answer: str, keyword: str) -> bool:
    """匹配文本关键词；纯数字使用数值边界，避免把 9 错配到 1997。"""
    if not keyword:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", keyword):
        pattern = rf"(?<![\d.]){re.escape(keyword)}(?![\d.])"
        return re.search(pattern, answer) is not None
    return keyword in answer


def score_answer_keywords(
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


def score_retrieval(sources: list[dict], spot_names: list[str]) -> tuple[float, list[str]]:
    """检索精度：期望景点名是否出现在检索结果中。"""
    if not spot_names:
        return 1.0, []
    all_content = " ".join(s.get("content", "") for s in sources)
    hit_spots = [name for name in spot_names if name in all_content]
    return len(hit_spots) / len(spot_names), hit_spots


def check_refusal_correct(answer: str, refused: bool, should_refuse: bool) -> bool:
    """边界题：判断是否正确拒答。"""
    if not should_refuse:
        return not refused
    # 应拒答的题：检查回答中是否包含拒答标志
    refusal_markers = [
        "无法提供", "无法回答", "不能回答", "不能帮", "暂未找到", "暂时没有",
        "超出我的", "超出了我的", "不在我的", "不在讲解范围", "不涉及景区",
        "请咨询景区", "换个景点", "换一个景点",
    ]
    return refused or any(marker in answer for marker in refusal_markers)


# ──────────────────────────────────────────────
# 单配置评测
# ──────────────────────────────────────────────
def run_config(
    base_url: str, config: dict, dataset: list[dict],
    skip_retrieval: bool, progress_label: str,
) -> dict[str, Any]:
    config_name = config["name"]
    fast = config["fast"]
    top_k = config["top_k"]

    results: list[dict[str, Any]] = []
    total = len(dataset)

    for idx, item in enumerate(dataset):
        qid = item["id"]
        question = item["question"]
        expected_keywords = item.get("expected_keywords", [])
        expected_keyword_groups = item.get("expected_keyword_groups")
        spot_names = item.get("spot_names", [])
        should_refuse = item.get("should_refuse", False)

        try:
            chat = request_chat(base_url, question, fast=fast, top_k=top_k)
            answer = chat["answer"]
            refused = chat["refused"]
            sources = chat["sources"]
            provider = chat["provider"]
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
            results.append({
                "id": qid, "question": question, "category": item["category"],
                "answer": "", "error": str(exc),
                "answer_score": 0, "answer_matched": [], "answer_ok": False,
                "retrieval_score": 0, "retrieval_matched": [], "retrieval_ok": False,
                "refusal_correct": False, "provider": "",
            })
            print(f"  [{progress_label}] ({idx+1}/{total}) {qid} ERROR: {exc}")
            continue

        # 回答精度评分
        if should_refuse:
            answer_score = 1.0 if check_refusal_correct(answer, refused, True) else 0.0
            answer_matched = []
        else:
            answer_score, answer_matched = score_answer_keywords(
                answer,
                expected_keywords,
                expected_keyword_groups=expected_keyword_groups,
            )
        answer_ok = answer_score >= PASS_THRESHOLD

        # 检索精度评分
        if skip_retrieval or should_refuse:
            retrieval_score = 1.0
            retrieval_matched = []
        else:
            retrieval_score, retrieval_matched = score_retrieval(sources, spot_names)
        retrieval_ok = retrieval_score >= PASS_THRESHOLD

        # 边界题拒答判断
        refusal_correct = check_refusal_correct(answer, refused, should_refuse)

        results.append({
            "id": qid, "question": question, "category": item["category"],
            "difficulty": item.get("difficulty", ""),
            "answer": answer[:500],
            "provider": provider,
            "answer_score": round(answer_score, 3),
            "answer_matched": answer_matched,
            "answer_ok": answer_ok,
            "retrieval_score": round(retrieval_score, 3),
            "retrieval_matched": retrieval_matched,
            "retrieval_ok": retrieval_ok,
            "refusal_correct": refusal_correct,
            "should_refuse": should_refuse,
            "source_count": len(sources),
        })

        mark = "PASS" if answer_ok else "FAIL"
        if should_refuse:
            mark = "REFUSE-OK" if refusal_correct else "REFUSE-FAIL"
        print(f"  [{progress_label}] ({idx+1}/{total}) {qid} {mark} "
              f"ans={answer_score:.2f} ret={retrieval_score:.2f} "
              f"prov={provider}")

    # 汇总统计
    answer_pass = sum(1 for r in results if r["answer_ok"])
    retrieval_pass = sum(1 for r in results if r["retrieval_ok"])
    refusal_pass = sum(1 for r in results if r.get("should_refuse") and r["refusal_correct"])
    refusal_total = sum(1 for r in results if r.get("should_refuse"))

    # 分类别统计
    from collections import defaultdict
    cat_stats: dict[str, dict[str, float]] = defaultdict(lambda: {"total": 0, "pass": 0, "sum_score": 0.0})
    for r in results:
        cat = r["category"]
        cat_stats[cat]["total"] += 1
        if r["answer_ok"]:
            cat_stats[cat]["pass"] += 1
        cat_stats[cat]["sum_score"] += r["answer_score"]

    summary = {
        "config": config_name,
        "fast": fast,
        "top_k": top_k,
        "total": total,
        "answer_accuracy": round(answer_pass / total, 4) if total else 0,
        "retrieval_accuracy": round(retrieval_pass / total, 4) if total else 0,
        "refusal_accuracy": round(refusal_pass / refusal_total, 4) if refusal_total else 1.0,
        "answer_pass": answer_pass,
        "retrieval_pass": retrieval_pass,
        "refusal_pass": refusal_pass,
        "refusal_total": refusal_total,
        "avg_answer_score": round(sum(r["answer_score"] for r in results) / total, 4) if total else 0,
        "avg_retrieval_score": round(sum(r["retrieval_score"] for r in results) / total, 4) if total else 0,
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


# ──────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="景区导览问答多模式对比评测")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端 API 地址")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="评测集 JSON 路径")
    parser.add_argument("--limit", type=int, default=0, help="只评测前 N 条，0=全部")
    parser.add_argument("--configs", default="", help="逗号分隔的配置名，空=全部")
    parser.add_argument("--skip-retrieval", action="store_true", help="跳过检索精度评测")
    parser.add_argument("--output", type=Path, default=REPORT_PATH, help="报告输出路径")
    args = parser.parse_args()

    # 加载数据集
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.limit > 0:
        dataset = dataset[:args.limit]
    print(f"评测集：{args.dataset}（{len(dataset)} 题）")

    # 选择配置
    if args.configs:
        names = [n.strip() for n in args.configs.split(",")]
        configs = [c for c in ALL_CONFIGS if c["name"] in names]
    else:
        configs = ALL_CONFIGS
    print(f"对比配置：{[c['name'] for c in configs]}")
    print(f"跳过检索评测：{args.skip_retrieval}")
    print()

    # 健康检查
    try:
        _post_json(args.base_url, "/api/rag/search", {"query": "灵山大佛", "top_k": 1}, timeout=10)
        print("后端健康检查：通过\n")
    except Exception as exc:
        print(f"后端健康检查失败：{exc}")
        print("请确保后端服务已启动。")
        sys.exit(1)

    # 逐配置评测
    all_summaries: list[dict[str, Any]] = []
    for config in configs:
        print(f"\n{'='*60}")
        print(f"评测配置：{config['name']}  (fast={config['fast']}, top_k={config['top_k']})")
        print(f"{'='*60}")

        started = time.perf_counter()
        summary = run_config(
            args.base_url, config, dataset,
            skip_retrieval=args.skip_retrieval,
            progress_label=config["name"],
        )
        elapsed = time.perf_counter() - started
        summary["elapsed_seconds"] = round(elapsed, 1)
        all_summaries.append(summary)

        print(f"\n  回答准确率：{summary['answer_accuracy']:.2%} ({summary['answer_pass']}/{summary['total']})")
        print(f"  检索准确率：{summary['retrieval_accuracy']:.2%} ({summary['retrieval_pass']}/{summary['total']})")
        print(f"  拒答正确率：{summary['refusal_accuracy']:.2%} ({summary['refusal_pass']}/{summary['refusal_total']})")
        print(f"  平均回答得分：{summary['avg_answer_score']:.4f}")
        print(f"  平均检索得分：{summary['avg_retrieval_score']:.4f}")
        print(f"  耗时：{elapsed:.1f}s")

    # 保存详细报告
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset_size": len(dataset),
        "configs": all_summaries,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n详细报告已保存：{args.output}")

    # 打印对比汇总表
    print(f"\n{'='*80}")
    print("对比汇总")
    print(f"{'='*80}")
    header = f"{'配置':<14} {'回答准确率':>10} {'检索准确率':>10} {'拒答率':>8} {'均回答分':>8} {'均检索分':>8} {'耗时':>6}"
    print(header)
    print("-" * 80)
    for s in all_summaries:
        row = (
            f"{s['config']:<14} "
            f"{s['answer_accuracy']:>10.2%} "
            f"{s['retrieval_accuracy']:>10.2%} "
            f"{s['refusal_accuracy']:>8.2%} "
            f"{s['avg_answer_score']:>8.4f} "
            f"{s['avg_retrieval_score']:>8.4f} "
            f"{s.get('elapsed_seconds', 0):>5.1f}s"
        )
        print(row)

    # 分类别对比
    print(f"\n{'='*80}")
    print("分类别准确率对比")
    print(f"{'='*80}")
    all_cats = sorted(set(cat for s in all_summaries for cat in s.get("category_breakdown", {})))
    if all_cats:
        cat_header = f"{'类别':<14} " + " ".join(f"{s['config']:>12}" for s in all_summaries)
        print(cat_header)
        print("-" * (14 + 13 * len(all_summaries)))
        for cat in all_cats:
            row = f"{cat:<14} "
            for s in all_summaries:
                val = s.get("category_breakdown", {}).get(cat, {})
                acc = val.get("accuracy", 0)
                row += f"{acc:>11.1%} "
            print(row)

    print(f"\n报告文件：{args.output}")


if __name__ == "__main__":
    main()
