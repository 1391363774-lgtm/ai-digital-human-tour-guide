"""Validate trusted fixture data only. NEVER run an agent patch with this tool.

Executing untrusted generated code requires the sandbox described in README.
This self-check is a dataset quality check, not a code-agent evaluation.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    task_bytes = (HERE / "tasks.json").read_bytes()
    oracle_bytes = (HERE / "acceptance.json").read_bytes()
    tasks = json.loads(task_bytes)
    oracle = json.loads(oracle_bytes)
    assert len(tasks) == len({item["id"] for item in tasks}) == 20
    assert sum(item["split"] == "development" for item in tasks) == 12
    assert sum(item["split"] == "acceptance" for item in tasks) == 8
    assert {item["id"] for item in tasks} == set(oracle)
    records = []
    for task in tasks:
        hidden = oracle[task["id"]]
        assert len(hidden) >= 3
        visible_args = [item["args"] for item in task["visible"]]
        assert all(item["args"] not in visible_args for item in hidden)
        namespace = {}
        exec(compile(task["source"], task["id"], "exec"), namespace)
        failures = 0
        for case in hidden:
            values = copy.deepcopy(case["args"])
            try:
                answer = namespace[task["function"]](*values)
                failed = answer != case["expected"] or values != case["args"]
            except Exception:
                failed = True
            failures += failed
        assert failures, f"fixture has no independently reproduced bug: {task['id']}"
        records.append({"id": task["id"], "independent_cases": len(hidden), "buggy_fixture_failures": failures})
    report = {"kind": "trusted_fixture_selfcheck_not_agent_performance", "tasks": 20,
              "development": 12, "acceptance": 8, "independent_cases": sum(len(x) for x in oracle.values()),
              "tasks_sha256": hashlib.sha256(task_bytes).hexdigest(),
              "acceptance_sha256": hashlib.sha256(oracle_bytes).hexdigest(), "records": records,
              "model_comparison": "not_run", "agent_success_rate": None, "model_tokens": None, "model_cost": None}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "records"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
