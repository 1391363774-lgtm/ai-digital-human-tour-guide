# 评测数据

- `qa_testset.json`：100 题项目回归评测集。
- 当前运行入口：`python 评测包/eval.py --mode backend --api-url http://127.0.0.1:8080/api/chat/send --dataset data/eval/qa_testset.json --output .runtime/eval.json`。
- 完整方法、指标边界和本轮基线见 `docs/IMPROVEMENTS-20261023.md`。两个qa_testset.json副本当前SHA-256相同，未为提高分数修改参考答案。

`eval_report*.json` 是包含模型回答的运行产物，默认不会提交仓库。若需引用结果，请记录模型、知识库版本、参数、时间和评分器版本。
