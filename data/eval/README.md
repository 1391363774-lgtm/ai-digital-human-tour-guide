# 评测数据

- `qa_testset.json`：100 题项目回归评测集。
- 运行入口：`python scripts/eval_qa_accuracy.py --base-url http://localhost:8000`。
- 完整方法、指标边界和历史基线见 `docs/EVALUATION.md`。

`eval_report*.json` 是包含模型回答的运行产物，默认不会提交仓库。若需引用结果，请记录模型、知识库版本、参数、时间和评分器版本。
