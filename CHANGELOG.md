# 变更记录

## [Unreleased]

### Added

- 初始化项目文档体系。
- 初始化前端、后端、AI、数据、脚本、测试目录。
- 添加 Docker Compose 基础服务。
- 添加 FastAPI 配置、日志、统一响应和健康检查。
- 添加 SQLAlchemy 核心模型与 Alembic 初始迁移。
- 添加官方灵山胜境景点数据导入脚本，支持资料包 dry-run 解析。
- 添加知识库上传、文档解析、切分、RAG 检索与 Chroma 索引服务。
- 添加 OpenAI 兼容 LLM 客户端和无 Key 本地降级问答。
- 添加文本问答、会话历史、路线推荐、ASR、TTS 协议与 2D 数字人页面。
- 添加知识库后台、景点后台、收藏、历史记录、游客反馈页面。
- 添加反馈情绪分析、满意度统计、游客行为 CSV 导入和运营数据大屏。
- 添加 `scripts/smoke_test.py` 和 `data/raw/sample_visitor_events.csv`。
- 添加前端 Vite 入口、TypeScript 配置和 Vue module shim。
- 添加后端 `requirements.txt`，容器启动前自动执行 Alembic 迁移。
