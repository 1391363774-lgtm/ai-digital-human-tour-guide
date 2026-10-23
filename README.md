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
- Markdown/JSON/已发布 SQL 知识 → 有重叠分块 → TF-IDF；可配置 DashScope embedding + numpy 余弦。数据库版本驱动完整快照，变更/删除/重分块后刷新，向量缓存绑定模型和维度。**没有实际接通 Milvus/Redis。**
- 游客由浏览器 capability 隔离；管理接口要求服务端密钥。SSE 增量解析、请求取消、旧请求保护，TTS 去重、有界并发与队列，停止后清理音频及口部状态。
- Live2D 是 2D 渲染；口部驱动为词边界/拼音规则或文本时长估算，不是音素强制对齐。PhotoHuman 是图片后备形变。
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

本地已通过 38 个后端、11 个前端回归，TypeScript 共享运行时类型检查及 15 页静态构建。测试不调用外部模型；真实 socket 回归检查进度/取消。100 题数据及独立评测包保留，未运行完整质量评分，不能写“100 项全部通过”或准确率。

CI 见 [.github/workflows/offline-regression.yml](.github/workflows/offline-regression.yml)：Windows/Linux 后端、前端交互/类型/构建、Docker 构建与 runner 内演示冒烟。Docker 默认 loopback、单进程、DEMO_MODE=true；`docker compose config --quiet` 已解析，本地未启动容器，不公开部署。

## 来源、恢复与贡献

脱敏源码清单见 [source-manifest](docs/migration/source-manifest.json)，旧文件逐项去向见 [迁移清单](docs/migration/old-file-disposition.csv)。旧实现可从 `backup/pre-new-source-20261023` 恢复；不删除仓库历史。docs/legacy 与 docs/source-README.md 是历史/原始说明，不能作当前能力或指标证明。

本轮修复由 AI 编程助手协助完成；个人简历必须以本人实际修改、讲解和验证记录为依据，不能直接写为独立设计实现。私人简历、学习记录和求职材料不纳入公开仓库。

**素材、Cubism SDK 与样例模型的再分发记录尚需人工核对，PR 保持草稿。** 参见 [来源与许可](THIRD_PARTY_NOTICES.md)。尚未确认默认分支包含本轮提交，不宣称替换完成。
