# 景区导览服务 AI 数字人

本项目面向第十五届中国软件杯 A5「景区导览服务AI数字人」赛题，构建面向游客和景区管理方的智能导览系统。

## 核心功能

- 多模态交互：文本、语音、数字人讲解。
- 景区智能问答：基于本地景区知识库与 RAG。
- 个性化路线推荐：按兴趣、时长、同行人群推荐。
- 管理后台：知识库、景点、数字人配置、反馈分析、数据大屏。
- 可部署：Docker Compose 一键启动。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Pinia + Element Plus |
| 后端 | FastAPI + SQLAlchemy + Alembic |
| 数据库 | PostgreSQL |
| 向量库 | Chroma |
| LLM | DeepSeek 主方案，Qwen 备用 |
| 语音 | faster-whisper ASR，云 TTS 或浏览器 TTS 降级 |
| 数字人 | MVP 2D 数字人，后续可接 LiveTalking/MuseTalk |

## 快速启动

```powershell
cp .env.example .env
docker compose up -d
```

后端容器启动时会自动执行 `alembic upgrade head`。如果只想检查接口，服务启动后运行：

```powershell
python scripts/smoke_test.py --base-url http://localhost:8000
```

导入官方景点资料：

```powershell
python scripts/import_official_data.py --source data/raw/cnsoftbei_a5_official_package.zip --commit
```

行为数据演示文件位于 `data/raw/sample_visitor_events.csv`，可在“行为数据”后台页面上传。

## 项目结构

详见 `ARCHITECTURE.md`。

## 当前阶段

当前 MVP 已覆盖景点数据导入、知识库解析切分、RAG 检索、文本问答、会话历史、路线推荐、语音输入、浏览器 TTS 降级、2D 数字人页面、知识库后台、景点后台、收藏、游客反馈、情绪与满意度分析、行为数据导入和运营数据大屏。

本地环境注意事项：

- Node/npm 与 Python 依赖安装依赖网络；当前环境曾出现 npm 静默挂起、pip 代理拒绝。
- Docker CLI 可用，但需要 Docker Desktop Linux Engine 处于运行状态才能构建和启动容器。
- LLM、云 TTS、地图 Key 均为可选；未配置时使用本地或浏览器降级能力。
