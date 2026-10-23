# 核查更正：以截图对应运行版为基准

## 来源

2026-10-23，用户截图 `127.0.0.1:8080/pages/home.html` 指向桌面侧栏首页和 Natori 男性 Live2D。用户随后明确确认新基准为 **21018015作品/灵山胜境AI数字人/**。

此前最初给定的 `21018015作品/21018015源码/` 实为另一份较早实现，其 Three.js 女性页面和占位后端结论**不适用于本次确认的运行版**。错误基准的本地工作区未推送，未用于本分支。不混入其后端重写。

远端 master 检查 SHA：`8f2b0d289fb969ae36bd14e0100ed5f219e94513`；旧开发目录 HEAD：`b6b769781b6bb9cfedf38ff2c461542ff8d0c28e`，检查时干净。远端恢复分支 `backup/pre-new-source-20261023` 指向前者。本目录从最新 master 独立克隆。确认运行版无 Git 历史，脱敏清单与校验见 source-manifest.json。

## 实际优点

- 前端为原生 HTML/CSS/JavaScript，桌面侧栏、轮播、Live2D Natori/切换、表情、拖动桌宠均有代码。核心 SDK 在 assets/vendor 本地加载；已用只读静态 HTTP 服务实际看到男性形象和截图对应首页。
- 后端有真实 FastAPI SSE/HTTP 路由，LLM 使用 httpx.AsyncClient；已有 primary/fallback 和两项离线故障注入脚本。不能说这个版本没有流式调用。
- RAG 真实读取 Markdown、结构化 JSON 和后台 published 知识；numpy cosine + DashScope embedding 调用、jieba TF-IDF 降级均有代码。Milvus/Redis 配置只是扩展占位，并非当前接通存储。
- SQLite 异步建表、知识 CRUD、持久化对话和统计查询是真实实现。TTS 调用 edge-tts，词边界结合拼音规则生成估算口型时间轴；ASR 为 Web Speech API，不是 Paraformer 已接通。

## 已定位的可靠性风险

- `llm_service._stream_provider` 把空白 token 当有效输出；丢弃畸形帧、不验证结束标记；部分输出异常被 stream_chat 吞掉，后续可能发正常 done。应迁移旧版空白/终态/不拼接约束。
- 模型流本身是异步 HTTP，**没有证据称它使用同步网络阻塞事件循环**。但 rag_service 的 jieba/numpy 构建、磁盘读写在 async 函数中同步执行，需要 CPU/磁盘隔离和实际并发测试。
- `knowledge.py` CRUD 只提交数据库，未立即更新已发布的内存索引；用户手动 rebuild 之前可能引用旧条目。RAG build 原位修改 chunks/tfidf/vectors，查询向量缓存没有 embedding 身份；重建与检索并发可错配。
- `chat.py` 信任任意 tourist_id；history 可枚举。knowledge/avatar 管理写接口和 analytics 原始反馈无鉴权；rate 可评价他人的反馈 ID。
- `chat_service` 为每句创建无上界 TTS task，无 finally 清理；前端 guide-app SSE 手写解析、无 AbortController，停止与新请求不能阻止旧请求回填；语音队列无界且停止可能留下 Promise 未解决。
- 原页面“已就绪·大模型在线”是写死文案，并非云服务实测；原 README 延迟/准确率及“严格同步”不作证据。词边界均分汉字 + 拼音规则不等于强制音素对齐；Live2D 嘴张度也不是 3D 数字人。

## 旧版保留价值及替换损失

旧 Vue 版本轮实际通过 106 个后端、17 个前端回归；其模型异步流/空流 failover、SSE UTF-8/CRLF 解析、缓存/向量版本、访问边界和音频生命周期测试可作迁移依据。只迁移适配后的通用实现和回归，不复制旧后端。旧版 SVG 源于默认 Live2D CDN 显式开关或加载降级；本地模型存在，不能据此说旧前端损坏。

替换退出：Vue 页面、PostgreSQL/Chroma/Alembic、旧收藏/反馈/历史/路线 API、旧 Docker 部署契约，不能承诺原接口兼容。新首页/地图/路线/拍照/扫码代码保留但各自按验证状态交付。旧公共技术资料存 docs/legacy；100 题/独立评测包保留，未全量评分。原游客级分析导出、数据库、音频/向量缓存均不纳入公开基准。逐文件删除和替代见 old-file-disposition.csv；全部历史可从恢复分支找回。

## 顺序与验收

1. 本次单独提交脱敏基线，页面保持原样；只验证无 Key 启动，不自动触发真实 TTS/模型。
2. 最小修复模型空流/白流、断流/部分终态；测试替身、真实 localhost 并发/取消。
3. 知识写鉴权、会话隔离、知识版本/原子快照、旧向量身份和回归。
4. 前端增量解析/取消/过期保护，TTS 有界队列/去重/彻底停止；保留默认 Live2D 和原视觉。
5. 后端离线回归、前端类型检查/构建/交互测试 CI；实际打开首页和完整问答链路。

真实外部 Qwen/DeepSeek/embedding/edge-tts、真实麦克风、完整 100 题、公开部署均需单列验证状态。素材、Cubism SDK 和样例模型的再分发许可未附完整证明，作为合并前人工审核事项，不自动合并。
