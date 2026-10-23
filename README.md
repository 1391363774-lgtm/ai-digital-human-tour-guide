# 灵山胜境 AI 数字人导览

第十五届中国软件杯 A5；河南财经政法大学；团队成员：刘翰、张越政；指导教师：张潇文。保留原作者及团队署名。

## 用户确认的新基准

2026-10-23 用户以实际运行截图更正来源为 `21018015作品/灵山胜境AI数字人/`。这是桌面侧栏、首页轮播和默认 Natori 男性 Live2D 的原生 JavaScript 版本，不是此前 `21018015源码` 的 Three.js 修仙女性旧页面，也不是 Vue 版本。

本提交为脱敏、可启动的原样逻辑基线。原作者声明见 docs/source-README.md，已核查范围见 docs/migration/COMPARISON.md。数据库、聊天、录音、TTS/向量缓存、.env、exe 和构建中间文件未导入。模型 .moc3/纹理是 Live2D 渲染资产，不是 AI 模型权重。

## 启动

`python -m venv .venv`，安装 `backend/requirements.txt` 后，执行 `python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8080`。打开 `http://127.0.0.1:8080/pages/home.html`。缺省无 Key 时应使用本地 TF-IDF；原逻辑 TTS 仍会访问 edge-tts 在线服务，离线验证必须在后续安全演示模式下执行。

不要复制原目录 .env。不要把本地素材存在、Key 已配置或测试替身通过等同于外部模型验证通过。没有本轮延迟/准确率或上线指标。100 题和独立评测包保留，未执行完整质量评测。

旧 Vue/PostgreSQL/Chroma/Alembic 功能退出当前项目树，恢复分支为 `backup/pre-new-source-20261023`，逐文件说明见 docs/migration/old-file-disposition.csv。不迁移旧数据库；需要单独设计真实数据迁移。

素材和 SDK 权利记录尚不完整，见 THIRD_PARTY_NOTICES.md。合并及公开部署前需要团队补齐。
