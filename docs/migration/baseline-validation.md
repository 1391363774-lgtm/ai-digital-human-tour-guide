# 正确运行版的基线验证

2026-10-23，Windows/Python 3.13.7。确认来源为 `21018015作品/灵山胜境AI数字人`，原目录保持只读，未运行其 exe、launcher 或构建脚本。

- 安装检查过的 backend/requirements.txt 到独立工作区 .venv，未安装 AI 模型。
- 使用 `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8082` 实际启动，未复制 .env、数据库、聊天、音频或向量缓存。
- 启动建表和无 Key TF-IDF 成功；健康、状态、首页、Natori model3 文件通过 HTTP 验证。首页及男性 Live2D 已由浏览器看到，与用户截图属于同一份源码。预览宽度不同时呈响应式布局。
- `PYTHONPATH=backend python backend/scripts/test_llm_failover.py` 的原有 HTTP 503 与 timeout 两项离线断言通过，MockTransport 不访问模型服务。
- 当前基线仍含源代码中的可靠性问题，见 COMPARISON.md；不作可部署版本。
- 未执行：真实云模型/embedding/edge-tts、真实麦克风、完整 100 题评分、容器启动、公开部署。未测首音频延迟，不能使用随附 README 的 1.5–3 秒指标。
