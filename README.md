# 灵山胜境 AI 数字人导览

第十五届中国软件杯 A5；河南财经政法大学。团队成员：刘翰、张越政；指导教师：张潇文。保留原作者与团队署名。

2026-10-23 按用户实际运行截图确认，以 `21018015作品/灵山胜境AI数字人/` 为基准：原生 HTML/JavaScript 桌面界面、Natori 男性 Live2D 和 FastAPI。比较、迁移风险、每阶段证据见 [核查](docs/migration/COMPARISON.md) 与 [交付记录](docs/migration/DELIVERY.md)。

## 无 Key 本地演示

需要 Python 3.13、Node 24。在仓库根目录执行：

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm run build
cd ..
./.venv/Scripts/python.exe scripts/run_demo.py --port 8080
```

Linux 使用 `.venv/bin/python`。打开 [游客首页](http://127.0.0.1:8080/pages/home.html) 或 [数字人导览](http://127.0.0.1:8080/pages/guide.html)。保留原 Live2D 和响应式风格，不默认切换简化人物。

**演示模式：本地 TF-IDF 检索与资料摘录，音频是合成测试音，未使用真实 LLM/自然语音/ASR。** 不读取原目录 .env，不下载 AI 权重。页面字体和天气小组件仍可能访问其原公共服务。管理默认关闭（503）；需要时在当前进程环境设置自己的 ADMIN_API_KEY 后重启，凭据不写前端。

## 当前实现与边界

- FastAPI SSE/HTTP，异步 httpx 模型请求；保留 primary → fallback → 本地摘录配置链。空白流可切换，部分回答失败会标记 partial，不拼接另一模型。
- Markdown/JSON/已发布 SQL 知识 → 有重叠分块 → jieba搜索分词与短窗口TF-IDF；可配置 DashScope embedding + numpy 余弦。数据库版本驱动完整快照，变更/删除/重分块后刷新，向量缓存绑定模型和维度。本地兜底按问题选择原文摘录及片段引用，仍不保证语义正确。**没有实际接通 Milvus/Redis。**
- 游客由浏览器 capability 隔离；管理接口要求服务端密钥。SSE 增量解析、请求取消、旧请求保护，TTS 去重、有界并发与队列，停止后清理音频及口部状态。
- Live2D 是 2D 渲染；音频口部驱动为词边界/拼音规则估算，不是音素强制对齐。事件间隔、暂停、缓冲与停止时闭嘴；浏览器自带语音无可用对齐时保持闭嘴并提示。PhotoHuman 是图片后备形变。
- 原生页面仍提供形象切换、表情、地图/路线、浏览器 ASR、拍照识景、扫码与管理界面；真实设备、外部供应商和自然语音尚未本轮实测，见交付记录。

真实模式可复制空白 `backend/.env.example` 后自行配置（不要提交），执行 `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8080`。配置 Key 的正常模式可能调用付费 LLM/embedding；本轮没有代为启用。仅“模型已配置”不代表真实服务验证成功。

当前按单 worker 验证；音频短期授权与语音限流使用进程内状态，多实例需另行设计。SQLite 不继承旧项目私有数据库；旧 PostgreSQL/Chroma/Alembic 接口和 Vue 功能没有兼容承诺。

## 验证

```powershell
./.venv/Scripts/python.exe -m pytest tests/backend -q
cd frontend
npm test
npm run build
cd ..
./.venv/Scripts/python.exe scripts/smoke_demo.py --base-url http://127.0.0.1:8080
```

2026-10-23 最新通过75个后端、18个前端回归，TypeScript共享运行时类型检查及15页静态构建。测试不调用外部模型；真实socket回归检查进度/取消。最新100题后端无Key诊断：请求成功100/100，关键词规则36/90，应拒答题5/10，正常题错误拒答8/90，仍有59个规则失败；相对本轮基线存在9个原通过题的退步，均完整保留。它们不是事实或语义准确率。见[增量检索记录](docs/RETRIEVAL-20261023.md)和[最新逐题报告](reports/eval/20261023-rag-final.json)；早期29/90、14/90基线及工程阶段记录保留于[前轮记录](docs/IMPROVEMENTS-20261023.md)。

评测命令：`python 评测包/eval.py --mode backend --api-url http://127.0.0.1:8080/api/chat/send --dataset data/eval/qa_testset.json --output .runtime/eval.json`。默认关闭TTS，每题使用独立游客凭据；直接模型模式用 `--mode openai --api-key-env EVAL_API_KEY --model <名称>`，不与后端RAG或浏览器离线结果混报。输出逐题JSON、汇总CSV、完整失败题；无适用样本以JSON null／CSV N/A表示。

CI 见 [.github/workflows/offline-regression.yml](.github/workflows/offline-regression.yml)：Windows/Linux 后端、前端交互/类型/构建、Docker 构建与 runner 内演示冒烟。Docker作业还运行全部100题无Key后端诊断并上传报告，只以请求／协议失败阻断，不以关键词分数冒充质量验收。固定音频的真实浏览器验收是本地人工触发，未纳入CI浏览器自动化。Docker默认loopback、单进程、DEMO_MODE=true；不公开部署。

## 来源、恢复与贡献

脱敏源码清单见 [source-manifest](docs/migration/source-manifest.json)，旧文件逐项去向见 [迁移清单](docs/migration/old-file-disposition.csv)。旧实现可从 `backup/pre-new-source-20261023` 恢复；不删除仓库历史。docs/legacy 与 docs/source-README.md 是历史/原始说明，不能作当前能力或指标证明。

本轮修复由 AI 编程助手协助完成；个人简历必须以本人实际修改、讲解和验证记录为依据，不能直接写为独立设计实现。私人简历、学习记录和求职材料不纳入公开仓库。

PR #2 已合并，迁移后的默认分支基准为 `26d77953fec0bac99df1eb18c9c342f16caff6ab`。本次增量改进使用独立分支，不重新迁移。**素材、Cubism SDK 与样例模型的再分发记录仍待人工核对；合并不代表授权核验完成。** 参见[来源与许可](THIRD_PARTY_NOTICES.md)。本轮PR状态以GitHub实际记录为准。
