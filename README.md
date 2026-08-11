# 灵山胜境景区导览服务AI数字人

**第十五届中国软件杯 A5 赛题参赛作品**

---

## 项目简介

灵山胜境景区导览服务AI数字人系统，是一款面向无锡灵山胜境景区的智能导览解决方案。系统以AI数字人"修贤"为交互核心，结合大语言模型（LLM）与向量检索（RAG）技术，为游客提供自然语言驱动的景区导览、知识问答和路线规划服务。

系统构建了灵山胜境专属知识库，涵盖灵山大佛、梵宫、九龙灌浴、五印坛城等核心景点的详细历史文化信息。通过Milvus向量数据库实现语义级知识检索，确保数字人回答的准确性和专业度，让游客获得沉浸式的文化导览体验。

本系统采用前后端分离架构，后端基于Python FastAPI构建，前端提供游客端导览界面和管理后台两个入口，支持数字人配置管理、知识库维护和数据分析等功能，形成完整的景区导览服务闭环。

---

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 前端 | HTML5 / CSS3 / JavaScript |
| 后端框架 | Python / FastAPI |
| 大语言模型 | 通义千问 qwen-vl-max（阿里云 DashScope） |
| 向量数据库 | Milvus v2.4 |
| 关系数据库 | MySQL 8.0 |
| 缓存 | Redis 7 |
| 容器化 | Docker / Docker Compose |
| Web服务器 | Nginx |
| 知识检索 | RAG（检索增强生成） |

---

## 项目结构

```
灵山胜境AI数字人/
├── docker-compose.yml          # 容器编排配置
├── README.md                   # 项目说明文档
├── backend/                    # 后端服务
│   ├── .env                    # 环境变量配置
│   ├── Dockerfile              # 后端镜像构建
│   ├── requirements.txt        # Python 依赖
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI 入口
│       ├── config.py           # 配置加载
│       ├── models/             # 数据模型
│       ├── routers/            # API 路由
│       ├── services/           # 业务逻辑
│       │   ├── llm_service.py      # LLM 调用服务
│       │   ├── rag_service.py      # RAG 检索服务
│       │   ├── knowledge_service.py # 知识库管理
│       │   └── avatar_service.py    # 数字人服务
│       └── utils/              # 工具函数
├── frontend/                   # 前端工程
│   └── dist/                   # 构建产物（Nginx 托管）
├── design/                     # 设计稿
│   ├── lingshan-guide/         # 游客端导览界面设计
│   ├── lingshan-admin/         # 管理后台界面设计
│   └── assets/                 # 设计资源
└── 知识库/                     # 灵山胜境知识库文档
    └── 灵山胜境完整知识库.md
```

---

## 快速启动

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

### 启动步骤

1. **克隆项目**

   ```bash
   git clone <仓库地址>
   cd 灵山胜境AI数字人
   ```

2. **配置环境变量**

   编辑 `backend/.env` 文件，填入有效的 LLM API Key：

   ```
   LLM_API_KEY=sk-your-actual-api-key
   ```

3. **一键启动所有服务**

   ```bash
   docker-compose up -d --build
   ```

4. **验证服务状态**

   ```bash
   docker-compose ps
   ```

   各服务端口：

   | 服务 | 端口 | 说明 |
   |------|------|------|
   | Frontend (Nginx) | 80 | 游客端导览界面 |
   | Backend (FastAPI) | 8000 | 后端API服务 |
   | MySQL | 3306 | 关系数据库 |
   | Redis | 6379 | 缓存服务 |
   | Milvus | 19530 | 向量数据库 |
   | Milvus Health | 9091 | Milvus 健康检查 |

5. **初始化知识库**

   首次启动后，需导入灵山胜境知识库数据：

   ```bash
   docker-compose exec backend python -m app.scripts.init_knowledge
   ```

### 停止服务

```bash
docker-compose down
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看单个服务日志
docker-compose logs -f backend
```

---

## API 接口文档概览

Base URL: `http://localhost:8000`

### 导览对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息，获取数字人回复 |
| POST | `/api/chat/stream` | 流式对话接口（SSE） |
| GET | `/api/chat/history/{session_id}` | 获取对话历史 |

### 景点导览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/spots` | 获取景点列表 |
| GET | `/api/spots/{spot_id}` | 获取景点详情 |
| POST | `/api/route/plan` | 智能路线规划 |
| GET | `/api/exhibits/{exhibit_id}` | 获取展品详情 |

### 知识库管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge/list` | 知识条目列表 |
| POST | `/api/knowledge/add` | 新增知识条目 |
| PUT | `/api/knowledge/{id}` | 更新知识条目 |
| DELETE | `/api/knowledge/{id}` | 删除知识条目 |
| POST | `/api/knowledge/import` | 批量导入知识库 |

### 数字人配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/avatar/config` | 获取数字人配置 |
| PUT | `/api/avatar/config` | 更新数字人配置 |
| GET | `/api/avatar/greeting` | 获取欢迎语设置 |

### 数据分析

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/analytics/overview` | 访问数据概览 |
| GET | `/api/analytics/hotspots` | 热门景点统计 |
| GET | `/api/analytics/questions` | 高频问题统计 |

---

## 团队信息

- **参赛赛题：** 第十五届中国软件杯 A5 赛题
- **出题企业：** 锐捷网络（苏州）有限公司
- **学校：** 河南财经政法大学
- **团队成员：** 张越政（技术负责）
- **项目定位：** 面向无锡灵山胜境景区的生产级智能导览系统

---

## 项目亮点

- ✅ **生产级架构**：Docker Compose 全栈编排，Milvus 向量库 + MySQL + Redis，Nginx 反向代理
- ✅ **双端完整产品**：游客导览界面 + 管理后台（知识库管理/数据分析/数字人配置）
- ✅ **大规模真实数据**：基于 140,000+ 游客行为记录和 22 个景点结构化知识库
- ✅ **多模态交互**：文字/语音/数字人三种交互方式，支持普通话与无锡方言
- ✅ **完整业务闭环**：RAG 智能问答 + 路线规划 + 景点推荐 + 数据分析

---

## License & 贡献

本项目为中国软件杯参赛作品，遵循 MIT 协议开源。欢迎 Star ⭐ 和 Fork，如有问题或建议请提 Issue。