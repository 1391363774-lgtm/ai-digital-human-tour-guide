> 原始附带说明，性能和能力声明未经本轮验证，不作验收证据。

# 灵山胜境景区导览服务AI数字人

**第十五届中国软件杯 A5 赛题参赛作品**

---

## 项目简介

灵山胜境景区导览服务AI数字人系统，是一款面向无锡灵山胜境景区的智能导览解决方案。系统以AI数字人"灵小仙"为交互核心，具备**语音、表情、口型同步的多模态交互能力**，为游客提供实时智能问答、个性化路线讲解、拍照识景、扫码定位等服务，并为景区管理方提供数据大屏与游客感受度分析。

### 核心亮点

| 亮点 | 说明 |
|------|------|
| 🎭 **真·口型同步数字人** | 自研2D Live2D风格数字人引擎：TTS词边界 + 拼音声韵母 → 12种中文视素，毫秒级口型同步；眨眼、呼吸、发丝飘动等生命感动效 |
| ⚡ **全链路流式管线** | LLM流式生成 → 按句切分 → 逐句TTS并发合成 → 就绪即播，承接语机制实现数字人**1.5~3秒开口**(远优于赛题5秒要求) |
| 🧠 **大模型 + RAG双引擎** | 通义千问 qwen-plus 对话生成 + qwen-vl-max 多模态图像理解（拍照识景）;DashScope Embedding语义检索 + TF-IDF降级引擎，断网可用 |
| 📍 **GPS弱信号解决方案** | 离线模式（本地知识库+浏览器TTS+估算口型） + 景点二维码扫码定位签到 |
| 📊 **真实数据管理后台** | 数据大屏、知识库维护、数字人形象/音色管理、游客感受度报告（大模型生成运营建议） |
| 📦 **双击即用** | 单exe一体化打包，评委零配置体验 |

---

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 数字人引擎 | 自研SVG参数化视素引擎（12视素 / 6表情 / 生命感动效） |
| 语音合成 TTS | edge-tts 神经网络语音（微软晓晓，词边界时间戳） |
| 语音识别 ASR | Web Speech API(Chrome/Edge) |
| 大语言模型 | 通义千问 qwen-plus（对话） / qwen-vl-max（多模态识图） — 阿里云 DashScope |
| 知识检索 | RAG：text-embedding-v3 语义向量（numpy余弦） + jieba TF-IDF降级 |
| 口型同步 | TTS WordBoundary + pypinyin声韵母→中文视素时间轴 |
| 后端框架 | Python / FastAPI / SSE流式 |
| 数据库 | SQLite（默认，零依赖） / MySQL（可选） |
| 前端 | HTML5 / CSS3 / 原生JavaScript / ECharts |
| 打包分发 | PyInstaller 单文件exe |

---

## 项目结构

```
灵山胜境AI数字人/
├── launcher.py                 # ★ 一体化启动器(双击即用)
├── build_exe.py                # PyInstaller打包脚本
├── README.md
├── backend/                    # 后端服务
│   ├── .env                    # 环境变量(LLM_API_KEY等)
│   ├── requirements.txt
│   ├── data/                   # 运行时数据(SQLite/向量缓存/TTS缓存)
│   └── app/
│       ├── main.py             # FastAPI入口(API+静态托管)
│       ├── core/               # 配置/数据库
│       ├── models/             # 数据模型
│       ├── api/                # chat/tts/knowledge/avatar/analytics
│       └── services/
│           ├── chat_service.py     # 流式问答编排(承接语+逐句TTS)
│           ├── llm_service.py      # LLM流式 + 多模态识图
│           ├── rag_service.py      # 双引擎RAG检索
│           ├── tts_service.py      # edge-tts + 中文视素时间轴 ★
│           └── sentiment.py        # 情感分析
├── design/lingshan-guide/      # 游客端前端
│   ├── pages/                  # home/guide/admin/route...
│   └── assets/
│       ├── digital-human.js    # ★ 数字人驱动引擎(口型/表情/动效)
│       └── knowledge.json      # 结构化景点数据(离线兜底)
└── 知识库/
    └── 灵山胜境完整知识库.md   # 7大板块知识语料
```

---

## 快速启动

### 方式一：直接运行（推荐）

```bash
pip install -r backend/requirements.txt
python launcher.py
```

浏览器自动打开 `http://127.0.0.1:8080/pages/home.html`

### 方式二：exe双击（评委版）

```bash
python build_exe.py        # 打包
# 将 dist/灵山胜境AI数字人.exe 放到项目根目录,双击运行
```

### 配置大模型Key

编辑 `backend/.env`:

```
LLM_API_KEY=sk-你的DashScope密钥
LLM_MODEL=qwen-plus
VLM_MODEL=qwen-vl-max
# 可选：配置第二家 OpenAI 兼容服务。主模型在首个有效 token 前失败时会切换。
LLM_FALLBACK_API_KEY=
LLM_FALLBACK_BASE_URL=
LLM_FALLBACK_MODEL=
```

> 未配置 fallback 时，主模型失败会降级为本地 TF-IDF 检索 + 知识库模板直答。流式响应一旦已经输出 token，为避免重复或矛盾内容，不会中途切换模型。

### 入口一览

| 入口 | 地址 |
|------|------|
| 游客首页 | /pages/home.html |
| 数字人导览 | /pages/guide.html |
| 管理后台 | /pages/admin.html |
| 系统状态 | /api/status |

---

## 核心API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | SSE流式问答（文本增量+情感标签+逐句语音口型） |
| POST | `/api/chat/vision` | 拍照识景（多模态大模型） |
| POST | `/api/tts` | 文本→语音+视素时间轴 |
| GET | `/api/tts/audio/{key}` | 音频文件 |
| GET/POST/PUT/DELETE | `/api/knowledge/items` | 知识库管理 |
| POST | `/api/knowledge/rebuild` | 重建检索索引 |
| GET/PUT | `/api/avatar/*` | 数字人形象/音色配置 |
| GET | `/api/analytics/dashboard` | 数据大屏 |
| GET | `/api/analytics/tourist-analysis` | 游客感受度 |
| POST | `/api/analytics/suggestions` | 大模型运营建议 |
| POST | `/api/analytics/checkin` | 景点扫码签到定位 |

---

## 团队信息

- **参赛赛题：** 第十五届中国软件杯 A5 赛题 · 景区导览服务AI数字人
- **队伍名称：** AI数字人-灵山胜境
- **学校/单位：** 河南财经政法大学
- **团队成员：** 刘翰 张越政
- **指导教师：** 张潇文
