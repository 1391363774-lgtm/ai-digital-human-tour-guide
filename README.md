# 灵山胜境 AI 数字人导游

面向第十五届中国软件杯 A5「景区导览服务 AI 数字人」赛题的完整原型。系统以数字人“灵汐”为交互入口，把景区知识检索、受约束的大模型回答、语音识别/合成、Live2D 展示、路线推荐和运营后台串成一条可运行链路。

> 本仓库强调可复现的工程实现：没有把模型训练、Milvus、Redis 等未落地能力写进技术栈。当前 RAG 使用 Chroma 与本地确定性向量，LLM 可接 DeepSeek/Qwen；无云端 Key 时仍可使用本地检索式回答和浏览器语音降级。

## 已实现能力

- **知识增强问答**：文档上传、解析切分、Chroma 索引、景点名增强检索、低置信度拒答和来源返回。
- **流式数字人讲解**：SSE 增量回答；首个完整句子就绪后提前启动分段 TTS，后续语音并行合成、顺序播放。
- **双通道模型容错**：按 `LLM_PROVIDER` 选择 DeepSeek 或 Qwen 为主通道；首个 token 前失败时切换另一通道，两者不可用时回退本地知识库回答。流已经输出后不会切换模型，避免内容拼接。
- **语音与形象**：faster-whisper 后端 ASR、edge-tts 中文语音、浏览器 Web Speech 降级；Live2D 口型随音频振幅驱动，模型加载失败时显示 SVG 后备形象。
- **游客服务**：景点查询、路线推荐、收藏、历史记录、拍照识景、游客反馈。
- **景区运营**：知识库/景点/数字人配置、行为数据导入、满意度与情绪统计、数据大屏。
- **两种交付方式**：Docker Compose（PostgreSQL）和 PyInstaller 本地包（SQLite）。

## 系统链路

```text
文字 / 麦克风 / 图片
        ↓
FastAPI API ── 会话、路线、反馈与运营数据
        ↓
Chroma 检索 + 景点词增强 + 低置信度边界判断
        ↓
DeepSeek → Qwen → 本地知识库回答
        ↓
SSE 文本流 → 分句 TTS → 顺序播放 → Live2D 口型与字幕
```

降级关系是单向且可解释的：云模型失败不影响本地知识库回答，edge-tts 失败不影响文字展示，Live2D 加载失败不影响 SVG 角色与核心问答。

## 技术栈

| 模块 | 当前实现 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、Pinia、Element Plus |
| 数字人 | Live2D Cubism Web、Web Audio API、SVG fallback |
| 后端 | FastAPI、SQLAlchemy、Alembic、SSE |
| RAG | Chroma、本地 hash embedding、词法检索与景点名增强 |
| LLM / VLM | DeepSeek 与通义千问 OpenAI-compatible API、Qwen-VL |
| ASR / TTS | faster-whisper、edge-tts、浏览器 Web Speech fallback |
| 数据库 | PostgreSQL（容器）/ SQLite（本地打包） |
| 交付 | Docker Compose、PyInstaller |

## 快速启动

### Docker Compose

```powershell
git clone https://github.com/1391363774-lgtm/ai-digital-human-tour-guide.git
cd ai-digital-human-tour-guide
Copy-Item .env.example .env
docker compose up -d --build
```

启动后访问：

- 游客端：`http://localhost:5173`
- 后端接口文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

模型 Key 均为可选。若需要云端回答，在 `.env` 中至少配置一个：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=
QWEN_API_KEY=
```

### 本地开发

后端需要 Python 3.11+，前端需要 Node.js 20+：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Set-Location backend
alembic upgrade head
fastapi dev app\main.py
```

另开一个终端：

```powershell
Set-Location frontend
npm install
npm run dev
```

导入赛题景区资料后可构建索引：

```powershell
python scripts\import_official_data.py --source <资料包.zip> --commit
python scripts\build_index.py
```

## 100 题评测集

仓库提供 100 题中文评测集，覆盖事实、景点介绍、文化背景、跨景点比较、路线、口语化改写和超范围拒答 7 类问题：

```powershell
python scripts\eval_qa_accuracy.py --base-url http://localhost:8000
```

既有基线报告中，`LLM + top_k=5` 的关键词回答通过率为 **75%**、检索命中率为 **94%**、边界题拒答率为 **100%**（2026-07-30，100 题）。这些数字是自动关键词/检索代理指标，不等同于人工事实准确率；评测器现已增加数字边界与同义词组规则，修改模型、知识库或评分器后应重新运行。详见 [评测说明](docs/EVALUATION.md)。

另有可移植的 [评测包](评测包/README.txt)，只依赖 Python 标准库，可测试本项目或其他 HTTP 问答接口。

## 项目结构

```text
backend/                 FastAPI、数据库、RAG、LLM、语音服务
frontend/                Vue 游客端、数字人页与管理后台
ai/prompts/              受约束的景区导游提示词
data/eval/               100 题评测集
scripts/                 数据导入、索引、冒烟测试与评测脚本
评测包/                  独立可移植评测工具
docs/                    架构、部署、演示和评测文档
```

更多接口见 [API.md](API.md)，部署细节见 [DEPLOYMENT.md](DEPLOYMENT.md)，架构说明见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 团队

- 赛题：第十五届中国软件杯 A5 · 景区导览服务 AI 数字人
- 学校：河南财经政法大学
- 成员：刘翰、张越政
- 指导教师：张潇文

## 使用边界

- 本项目是比赛原型，不应替代景区官方票务、交通、安全或宗教事务说明。
- 票价、开放时间、演出场次等时效信息应以景区官方渠道为准。
- `.env`、真实游客数据、运行数据库和完整评测输出不会提交到仓库。
- Live2D 模型与素材需遵守各自许可；二次发布前请重新核对素材授权。
