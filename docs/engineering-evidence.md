# 工程证据（持续更新）

## 基线与边界

2026-10-22 通过 Git 远端/API 核对：master = `f387e0deadcb97b89dca0f4994d6eda88d883991`；已有 PR #1 = `68cb7da0d4167ae14e84a5c02ca89b57b953081e`，工作区干净。
技术栈为 FastAPI/Vue/Chroma/local_hash/DeepSeek/Qwen/PostgreSQL 或 SQLite。
local_hash 是确定性散列，不是预训练语义模型。已有团队署名保留。

此前 PR 的异步模型网络流、空响应切换、SQL 知识版本缓存已保留，本次基线重跑 `python -m pytest tests/backend -q`：52 passed / 13.13s；`pip check` 通过。
首次受限执行因 Windows pytest 临时目录权限得到 35 passed / 17 errors；经正常权限审批重跑，未修改测试以规避错误。
历史慢流对比见 [已有证据](RELIABILITY_REVIEW.md)。单机模拟时序不代表真实模型性能。

## S1：SSE 协议与回答终态（P0）

原实现：前端只接受 `data: `、忽略 JSON 错误和 EOF 尾部，无 AbortSignal/reader 清理。后端对部分回答调用普通持久化，拒答/失败/取消没有终态记录。
修复前新增协议测试 5/5 失败，终态测试 5/5 失败；这是 10 个断言场景，不是 10 个独立产品缺陷。

选择：保留现有 JSON SSE 事件类型，增加 request_id/source/done.status；共有 UTF-8 增量行解析器处理 CRLF、多行 data、尾部、上限、显式解析错误与 finally 清理。
后端 `Message` 增加 status/request_id/error_code；迁移 0004。旧记录状态默认 completed，无法追溯历史回答当时是否完整。
开始计时在 prepare_stream 前。SQLAlchemy Session 仅在顺序的工作线程调用中使用，不与模型网络 I/O 并行；会话 ID 在工作线程内快照，避免过期 ORM 属性在事件循环隐式查询。
取消时关闭上游，然后在 shield 内保存 cancelled；未完成回答不进入后续 assistant 上下文。进程被杀、数据库不可用仍可能无法写入审计，不能承诺崩溃后恰好一次。
错误响应仅含稳定错误码，日志记录异常类型和 request_id；不返回供应商异常字符串或记录提问正文。

验收命令（仓库根目录；Windows 将 python 换为 `.venv\Scripts\python.exe`）：

```text
python -m pytest tests/backend -q
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm test
npm run build
```

增加开发依赖 Vitest 4.0.18（锁文件）；无新收费服务、模型 Key。CI 增加 Node 24 前端测试及类型/构建。生产依赖保持原栈。
本地修复后：后端 57 passed / 14.31s，随后实际落库测试 1 passed / 1.93s；前端 5 passed；`npm run build`（含 vue-tsc）通过 / Vite 16.20s。依赖包注释与大 chunk 警告仍存在。
构建诊断：旧 dist 存在时本机 Node 24.12.0 多次以原生崩溃码 0xC0000409 退出；换新输出目录成功，把旧产物保留到忽略的 `.local-build` 后标准命令成功。底层崩溃原因未进一步确认；没有关闭正式压缩/类型检查规避验证。
协议测试使用内存 ReadableStream；ASGI 测试使用假模型；原有并发探针使用真实 localhost HTTP。这些不能替代真实云模型/浏览器音频验收。

## 下一轮已确认风险与优先级

- P0 管理写接口无鉴权、历史可枚举：需服务端权限与会话隔离；收益是阻止未授权读写，成本为请求契约/前端凭据入口/迁移及回归。不能公开部署当前原型。
- P0 索引只有 upsert、删除后物理向量残留：已有 SQL 校验避免旧引用返回；还需可重试清理与部分失败测试。多 worker 需共享 SQL 版本；本地 Chroma 不视为已验证跨进程共享写入。
- P0/P1 播放/取消状态耦合：首段结束置 idle、失败可能重播整段；需有界队列和请求代次。
- P1 口型依赖随机字符规则与估算时长：将采用实际音频能量；不称音素对齐。
- P1 fast 固定回复/静态摘要可能绕过知识：必须显式路径、消除过期资料与证据混淆。
- P2 语义 embedding/精细 viseme 暂缓：先有固定对比数据，再决定成本与模型授权。

后续结果记录在 [进度](progress.md)。所有本次自动测试和改动为 AI 辅助执行，用户亲自验收另行记录，不由提交存在推定。

## S2：权限、知识一致性与引用（P0）

原实现：管理写 API 无鉴权，会话/历史可按整数 ID 枚举，收藏共用 anonymous；知识索引主要 upsert；向量 metadata 和静态景点摘要可被当成来源。

复现：访问测试初次 2 failed；索引精选初次 4 failed；无知识仍回答/本地兜底返回 system 文本等 grounding 场景初次 4 failed。之后访问/上传/迁移 6 passed，索引/缓存/HTTP 组合 28 passed，grounding 扩展至 6 passed。参数化实例数量不等于独立 bug 数量。

修改与核心逻辑：

- `core/access.py`、相关 routes：管理员密钥 constant-time 比较，未配置默认关闭；游客随机凭据的 SHA-256 存 SQL，会话/历史/收藏按其过滤，跨游客 ID 返回 404。迁移 0005 保留旧无归属记录，但不公开认领。前端管理员密钥只存当前页内存。
- `knowledge_repository.py`：所有知识写入先锁共享版本行，SQL 变更、版本递增、旧向量清理任务一起提交；SQLite 跨进程锁实测。回滚不发布索引成功。
- `knowledge_index_service.py` / `vector_store_service.py`：collection 标识 local_hash v1 / 384 维；每次写入使用独立 attempt ID，数量必须完整。迁移 0006 的待清理表支持部分失败及跨 Session 重试。删除/重分块后 SQL 引用立即消失；物理清理失败返回 pending，不谎称清空。全重建收集孤儿。
- `rag_service.py`：从当前 SQL 生成 doc/chunk ID、标题、更新时间、版本与摘录，不信任向量自报来源；缓存返回深拷贝。公开 source API 不输出服务器文件路径。它返回当前片段，不是不可变版本存档。
- `chat_service.py` / `prompt_service.py`：fast 与普通路径均要求真实检索，回答路径不再注入硬编码摘要。动态票价/场次不猜。资料 JSON 与 system 分离，内部 reference_data 标记防止游客伪造资料被本地兜底接受。超长/空白证据拒答。结构隔离和 Vue 转义不是“云模型绝对抗注入”的证明。

收益是阻止未授权读写、旧引用与伪来源；成本是两个迁移、HTTP 凭据契约变化及向量重建，无新增服务。升级前备份数据库。索引时持有 SQL 写锁，仅适合小型本地索引，不要放远程 embedding 网络请求。真实 PostgreSQL/Chroma 多 worker 未实测。进程在向量写入与登记清理间被杀仍可能产生孤儿，全重建可回收，但不是分布式原子事务。

## S3：播报生命周期与音量口型（P0/P1）

原实现：字符规则/估算时长/随机值生成嘴型，闭嘴 0 被默认值替换；首句 ended 可能让整问答提前 idle，失败可能从头重播；后端 semaphore 限制运行数，却仍创建全部任务。

新增 `frontend/src/audio/{speech-queue,audio-player,energy-mouth,sentence-buffer}.ts`，接入 AvatarView：

- 队列容量 4（含在播段），request_id + 单调 segment_id 拒绝旧请求、重复和乱序，满队列等待；一个消费者逐段合成/播放，Promise 真正等 ended。
- 停止传播至文本 fetch/reader、TTS、队列、HTMLAudio 和动画；迟到结果丢弃；释放监听、定时器、object URL 和音频节点。页面隐藏/离开停止，麦克风迟到回调有代次保护。失败保留文字，不重播旧段。
- 口型根据实际 PCM 的 RMS、静音阈值和平滑计算；currentTime 推进才更新，静音/暂停/等待/结束/取消复位 0。不是音素对齐。
- 分句保留数字、标点与尾段，`1.` + `5` 跨块不被拆句。
- 后端 speech_service 校验输入而不静默截断，缓存限制条数/字节；有限 pending tasks，finally cancel + gather，上游显式关闭。Windows 超限临时上传先关闭句柄再删除。
- speech 路由在响应头前也监听断连；NDJSON 含 request/segment ID，错误不伪造 done，不返回供应商异常正文。

语音后端初次 18 failed（含 12 个参数校验实例），修复后 18 passed；断连/模型协议专项 6 passed。前端使用确定性假 Audio 对象与固定 PCM 验证能量、队列和资源清理，不是云 TTS 性能测试。

浏览器实际验收：2026-10-22/23，本机 IAB、SVG、模拟模型和 16kHz 固定音调。看到文本与播放并行、引用展开、队列达到 4 后推进；停止后 pending=0/stopped/mouth=0。单次界面 first text 247ms、playing event 432ms、stop cleanup 0.6ms，仅为样例观察，不是性能提升或扬声器停声延迟。截图见 [实际停止画面](evidence/browser-stop.png)。小屏发现按钮与 request_id 溢出，已增加换行/可收缩布局。未制作视频，真实听感、硬件停声、自动播放受限设备仍待实测。

## S4：无 Key 启动与验收边界

`scripts/run_demo.py` 在独立目录建 SQLite/迁移至 0006/导入公开小样例，监听 127.0.0.1；不读取 .env，清空模型 Key，强制模拟模型和固定音调、关闭 ASR/VLM/在线预热。demo 走 SQL 词法，不依赖 Chroma；默认不加载 Live2D CDN。故障开关只有 demo + 管理密钥可用，限定单 worker。

`test_demo_smoke.py` 从新目录启动真实子进程，通过 localhost HTTP 验证引用、拒答、空流备用、WAV 静音、游客隔离及禁用 ASR。不是只 mock 函数；也不证明完整景区问答质量。新增配置/HTTP 头、迁移与兼容性见 README。

2026-10-23 本地完整回归 106 passed / 19.89s；pip check 无冲突；正式 vue-tsc + Vite 构建通过 / 7.56s。前端新增 NDJSON 回归后的最终数量见 progress。Windows Node24.12.0 覆盖旧 dist 再次以 0xC0000409 原生崩溃，保留旧生成物后同一命令成功；底层原因未确定，没有跳过压缩/类型检查。PURE 注释和大 chunk 警告仍存在。远端 CI 在干净 checkout 验证。

复现命令：

```text
python -m pip install -r requirements-test.txt
python -m pytest tests/backend -q --junitxml=test-results/backend.xml
python -m pip check
cd frontend
npm ci --ignore-scripts --no-audit --no-fund
npm test
npm run build
```

这些检查均无模型 Key/外部数据库。新增 Vitest 只是开发依赖；没有新增 Docker 服务或收费调用。仍未验收真实 DeepSeek/Qwen/Edge/faster-whisper/Chroma/PostgreSQL/Docker/exe；没有真实 usage 和费用收益数字。完整账号/生产限流/压缩文档资源隔离不足，不建议开放公网。

100 题的参考答案、来源和相关片段标注尚未补齐；没有当前版本的事实/引用支持率、Recall@k/MRR。独立验收集和 12 场景汇总诊断工具仍待交付，不把现有回归说成盲验收。语义模型/viseme/自动打断/AEC/大型 Agent 延后，先完成可复核资料评测。

### 三分钟演示

0:00–0:45：按 README 启动，说明“模拟模型 + 固定音调”，提问“介绍灵山大佛”，打开依据看文档/片段/版本。说明样例没有官方来源核验。

0:45–1:30：打开诊断面板，播放中停止，确认队列/口型复位，立即换问九龙灌浴。解释文本结束不等于播报结束。

1:30–2:00：纯文字提问“遥远火星隐秘景点在哪里”，看无资料拒答；问今日票价，看时效边界。

2:00–3:00：后端启动前设置自己的 ADMIN_API_KEY，另开终端使用同一环境变量执行：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/demo/fault -Headers @{'X-Admin-Key'=$env:ADMIN_API_KEY} -ContentType application/json -Body '{"fault":"empty"}'
```

再问已知景点，done 模型路径显示 simulated_model → local_fallback。改为 partial 展示首段后错误、不混新答案；结束改回 none。未配置密钥就跳过，不能关闭鉴权。故障是人工注入，不是实测云供应商宕机。
