"""Materialize ONE trusted task in a new local Git repository, never overwrite."""
import argparse
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = next(item for item in json.loads((HERE / "tasks.json").read_text(encoding="utf-8")) if item["id"] == args.task)
    target = args.output.resolve()
    if target.exists():
        raise SystemExit("output must be a NEW directory; existing work is never overwritten")
    (target / "src").mkdir(parents=True)
    (target / "tests").mkdir()
    (target / "src" / "__init__.py").write_text("", encoding="utf-8")
    (target / "src" / "guide_tools.py").write_text(task["source"], encoding="utf-8")
    (target / "TASK.md").write_text(task["prompt"], encoding="utf-8")
    cases = repr(task["visible"])
    test = (
        "import json\nimport unittest\nfrom src import guide_tools\n\n"
        "class VisibleTests(unittest.TestCase):\n"
        "    def test_examples(self):\n"
        f"        for case in {cases}:\n"
        "            with self.subTest(case=case):\n"
        "                args = json.loads(json.dumps(case['args']))\n"
        "                before = json.loads(json.dumps(args))\n"
        f"                self.assertEqual(guide_tools.{task['function']}(*args), case['expected'])\n"
        "                self.assertEqual(args, before, 'inputs must not be mutated')\n"
    )
    (target / "tests" / "test_visible.py").write_text(test, encoding="utf-8")
    (target / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    for command in (["git", "init", "--initial-branch", "task"], ["git", "add", "."],
                    ["git", "-c", "user.name=Benchmark Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", f"Fixed fixture {task['id']}"]):
        subprocess.run(command, cwd=target, check=True, capture_output=True)
    print(json.dumps({"task": task["id"], "split": task["split"], "workspace": str(target)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
