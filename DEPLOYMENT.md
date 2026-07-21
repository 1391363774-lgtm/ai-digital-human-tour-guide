# 部署说明

## 环境要求

- Docker
- Docker Compose
- Node.js 20+
- Python 3.11+

## 本地启动

```powershell
cp .env.example .env
docker compose up --build
```

后端容器会先执行 `alembic upgrade head`，再启动 FastAPI。

## 数据库迁移

容器内迁移：

```powershell
docker compose exec backend alembic upgrade head
```

本机迁移需要 Python 3.11+ 和后端依赖：

```powershell
cd backend
alembic upgrade head
```

## 数据导入

导入官方景点结构化资料：

```powershell
python scripts/import_official_data.py --source data/raw/cnsoftbei_a5_official_package.zip --commit
```

构建知识库向量索引：

```powershell
python scripts/build_index.py
```

行为数据演示文件：`data/raw/sample_visitor_events.csv`。启动前端后进入“行为数据”后台页面上传。

## 验证

```powershell
docker compose config
python scripts/smoke_test.py --base-url http://localhost:8000
```

## 常见问题

| 问题 | 原因 | 处理 |
|---|---|---|
| 后端连接数据库失败 | `.env` 数据库配置不一致 | 检查 `DATABASE_URL` |
| 前端无法访问后端 | CORS 或端口错误 | 检查 `VITE_API_BASE_URL` |
| Alembic 未发现模型 | 未导入模型元数据 | 检查 `backend/alembic/env.py` |
| `docker compose build` 无法连接 Docker Engine | Docker Desktop 未启动或 Linux Engine 未运行 | 启动 Docker Desktop 后重试 |
| `npm install` 长时间无输出 | npm registry 或代理异常 | 切换网络或 registry 后重试 |
| `pip install` 代理拒绝 | Python 包索引不可达 | 使用 Docker 构建，或修复代理后安装 |
