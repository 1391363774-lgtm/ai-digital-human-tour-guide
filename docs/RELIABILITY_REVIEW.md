# 工程交付说明 · 2026-10-20

> 历史阶段记录，保留原始结果以便审查。2026-10-22/23 已新增回答状态、鉴权、向量清理与音频生命周期；本文“尚未实现”的部分可能已被后续修复。当前行为与限制以 [工程证据](engineering-evidence.md) 和 [进度](progress.md) 为准。

## 基准与范围

远端：`https://github.com/1391363774-lgtm/ai-digital-human-tour-guide`。
本次由 `git ls-remote ... HEAD` 和克隆后的 `git rev-parse HEAD` 共同确认的基准：
`f387e0deadcb97b89dca0f4994d6eda88d883991`。
独立分支：`agent/reliability-20261020`，克隆初始 `git status --short` 为空。

真实基准技术栈：FastAPI/SSE、Chroma、local_hash embedding、DeepSeek/Qwen、SQLAlchemy，容器 PostgreSQL / 本地 SQLite。
不采用旧 GitHub 网页缓存中的 Milvus/MySQL/Redis 描述，也不把另一个 F 盘旧作品的实现混入本仓库。

范围为三个可靠性缺陷、离线回归、CI 配置和学习证据；不操作求职平台。没有重写前端、语音 SSE 或引入新外部服务。

## 原有能力与本次新增

原有：同步和流式模型客户端、首段前异常备用切换、本地兜底、RAG、30 分钟进程内检索缓存、上传/切块/索引/删除接口、3 个测试文件的 8 个测试实例、100 题问答评测集。

新增：异步模型 HTTP 流、明确关闭上游资源、有效文本判断、共享知识版本号、SQL 当前片段核对、回归与 CI。原有 8 项在独立环境实测通过，不能以“文件存在”代替这个结果。

这些新增代码和本次运行记录由 agent 完成；没有证据表明用户已经独立实现或亲自完成验证。用户能力状态见 MENTORING.md。

## R1：文本 SSE 阻塞与取消

需求：一个模型流等待网络时，健康检查和第二个流仍能推进；游客断开后上游停止读取并关闭。

失败原因：`async def event_stream()` 内普通 `for` 调用同步 `HTTPSConnection.readline()`。函数标记 async 不会把同步 socket 自动变成非阻塞。原来的 prepare/persist 也直接运行在事件循环。

最小修改：保留同步客户端给普通 HTTP 使用，新增 `achat_stream()`；云通道用 `httpx.AsyncClient.stream()` / `aiter_lines()`，本地非流式客户端放入线程池。路由的 SQL/检索准备与持久化串行放入线程池，不并发共享同一个 Session。`aclosing` 向下传播关闭；响应的 finally 显式关闭 body iterator，处理 ASGI 2.4 在 send 时抛错的分支，使用 AnyIO shield 确保清理完成。

没有用线程包住整个同步网络流：阻塞线程无法随客户端取消立即停止读取。异步 HTTP 读才是这一取消需求的直接实现。[HTTPX 官方异步与关闭说明](https://www.python-httpx.org/async/)。

协议保留 `conversation_id/text/refused/error/done`。中途模型错误保留已输出文字，不拼接新模型，也不把错误文案写成正常回答；取消不保存未完成回答。当前消息表没有“部分回答”状态，正常传播的中途错误仍可能持久化部分文本，后续需完善状态设计。

复现：`python scripts/probe_sse_concurrency.py --output <report.json>`。脚本实际启动本机 Uvicorn 和两个 HTTP SSE 请求；模型替身每流 10 段、每段 150ms，A 首段后断开。修复前用阻塞 sleep，修复后走真实异步 HTTP 解析器及假响应体。没有模型、数据库、Chroma、TTS 外部请求。

可审查证据：`evidence/reliability/sse-before.json`、`sse-after.json`，含客户端和服务端时间线。负的修复前 cancel-to-close 表示客户端能请求取消时上游早已读完，不能解读为“取消很快”。这些是本机合成场景单次采样，不是用户延迟或生产吞吐改善率。

最终留档采样：健康检查 1513.97ms → 16.53ms；第二流首段等待 3027.36ms → 169.28ms；修复后取消至上游关闭 9.86ms。A 上游读取从10段变为1段，两个上游都已关闭。不要把这一对合成样本计算成简历中的生产提升百分比。

回归同时覆盖 ASGI 2.4 send 异常、普通断连、异步 HTTP response 关闭、快答/拒答协议、持久化的线程位置。ASGI 2.4 清理测试曾在初版异步修复后仍失败，补响应 finally 后通过，说明“改成 async”本身还不够。

面试追问：await 在什么情况下让出事件循环？线程池为何不能取消阻塞 socket？为什么必须同时关闭生成器和 HTTP response？断连后数据库应保存什么状态？

## R2：空流没有备用回答

需求：空流、纯空白、首段前异常可以切换；出现有效文字后不拼接另一个模型。

失败原因：原逻辑把一次正常结束视为成功，而且任意 chunk（包括空白）都把 emitted 标记为 true。

修改：同步与异步流均跳过首段前空白，第一次非空白文字才标记 emitted；结束时仍无有效文字则抛 LLMClientError 进入下一通道。已有有效文字后的空格保留，避免把英文单词连在一起。普通 HTTP 也将空回答视为通道失败。

测试覆盖：空迭代、空字符串、纯空白、空白后异常、首段前网络超时/HTTP500、备用成功、首段后异常不调用备用、所有通道空、输出后空格保留；异步 HTTP 使用 MockTransport，不接触真实 Key。

面试追问：为什么不能在第一个字后继续切换？空白与无 token 有何区别？请求成功的 HTTP200 为什么不等于业务成功？

## R3：知识变更后的旧缓存与旧向量

需求：缓存后新增/修改/删除知识，再次检索立即看到新版本；独立 worker 不依赖人工清内存缓存。

原实现：缓存只有 query/top_k，TTL 30 分钟，修改路径没有失效；删除 SQL 文档也未移除 Chroma 旧向量。只清内存缓存仍可能把旧向量重新召回。

修改：新增单行 `knowledge_revision` 表及 Alembic 0003。新增上传记录、重分块、删除、索引完成在同一 SQL 事务中原子递增版本；空索引重建也递增。查询用独立短连接读取已提交版本，把“引擎实例、版本、query/top_k”放进缓存键。锁只保护内存缓存的读写和淘汰，不包住 SQL/网络 I/O。老查询只能写老版本键，不能污染新版本。

检索到的向量须在 SQL 中存在相同 vector_id 和相同内容，否则丢弃并继续原有词法检索。已重新切块但尚未重建向量时会使用新 SQL 内容；不会从 Chroma 复活已删除旧文。文档 version 在重分块时递增。

现有接口没有 PUT 文档内容的路径。“修改”的已有实现是更新文件后对同一文档重新切块，本次未虚构一个新的编辑接口。上传记录本身没有片段，需切块后才可检索；已有知识文件的上传目录与上传限制不变。

验证：真实临时 SQLite + HTTP 上传→切块→先缓存→替换文件→重分块→立即查询→索引→删除；另有两个 Session、独立子进程更新、在途旧查询与失败事务回滚测试。

并发语义：更新提交后开始的新查询读取新版本；与更新重叠的在途查询可能返回旧快照，但只会缓存到旧版本。没有声称实现所有请求的线性一致性。生产应使用默认 READ COMMITTED；自定义长事务/REPEATABLE READ 尚未验收。

剩余边界：Chroma 的物理旧条目尚未做垃圾回收，可能占空间和挤占候选，正确性由 SQL 核对保护；直接绕过 Repository 的 SQL 修改不会递增版本；内置 FAST_SPOT_SUMMARIES/fast 快答与 Chroma 本身不是这张知识表的实时镜像。此次保证的是数据库知识检索的新鲜度，不保证所有内置话术自动更新。

面试追问：为什么进程锁不能解决多 worker？版本递增为什么要和写操作一起提交？回滚后版本是否变化？SQL 与向量库不能同事务提交怎么办？旧请求晚返回会不会重新污染缓存？

## 测试、CI 与运行

可复制的最小环境（不加载 .env 的模型 Key）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m pytest tests/backend -q --junitxml=test-results/backend.xml
.\.venv\Scripts\python.exe scripts/probe_sse_concurrency.py --assert-responsive --output sse-local.json
git diff --check
```

Linux 替换为 `.venv/bin/python`。`tests/conftest.py` 显式清空两个 Key、使用 SQLite 并拒绝外部 socket 连接；独立 loopback 服务器只负责慢流测试。数据库 fixture 与 Chroma 替身在测试内创建，无需任何 Docker 服务。

CI：`.github/workflows/backend-regression.yml`，push/PR/手动触发，Windows/Linux × Python3.11/3.13，安装同一 requirements-test，上传 JUnit。首次本地交付时尚未推送；2026-10-20 按用户要求推送后，代码提交 `30f76a2c3bee04c3d5c1fe374e18488f2f72f52c` 的四种环境均已通过 [GitHub Actions](https://github.com/1391363774-lgtm/ai-digital-human-tour-guide/actions/runs/39394009525)。可复核状态记录见 `evidence/reliability/github-sync.json`。[GitHub 官方 Python CI 文档](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)。

本机最终实际输出：`52 passed in 12.82s`（8项原有、44项新增参数化测试实例）。完整依赖一致性检查为 `No broken requirements found`。修复前精选新增场景为22失败/4通过；该数量包含新异步API当时不存在的失败，不能全部等同22个独立产品bug。

生产新增直接依赖 httpx 与 anyio（原本可能通过 FastAPI 间接安装，现在显式声明）；测试环境单独固定版本。不新增模型 Key、环境变量或 Docker 服务。**已有数据库升级前备份，再运行 0003 迁移**；否则检索会报缺少版本表。新建本地 SQLite 的 create_all 路径会建立并初始化新表；已存在的打包数据库仍需迁移，旧 exe 不会自动获得源码改动。

源码启动（完整依赖，和离线回归环境分开）：

```powershell
python -m pip install -r backend/requirements.txt
$env:DATABASE_URL='sqlite:///./local-guide.db'
Set-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

该相对 SQLite 文件位于 backend/。无 Key 时用原有本地回答；知识需按原 README 上传/切块/索引。另开终端在 frontend/ 执行 npm install 和 npm run dev。Dockerfile 原本已在启动前运行 alembic，因此保留其部署方式；此次未构建镜像或实际部署 PostgreSQL/Chroma/ASR。完整 app 的 TTS 预热仍可能访问在线语音服务，离线回归刻意只装实际被测路由，没有把该启动行为冒充离线生产部署。

## 交付与未验收项

文件范围：

- `backend/app/api/routes/chat.py`：异步路由编排、线程池 SQL、显式关闭响应生成器。
- `backend/app/services/llm_client.py`：异步 HTTP、同步/异步有效文本判断与备用策略。
- `backend/app/core/knowledge_revision.py`、`models/knowledge.py`、`alembic/versions/0003_knowledge_revision.py`：共享版本与迁移。
- `repositories/knowledge_repository.py`、`services/knowledge_index_service.py`、`services/rag_service.py`：同事务版本递增、版本缓存键与当前 SQL 片段校验。
- `backend/requirements.txt`、`backend/pyproject.toml`、`requirements-test.txt`：显式运行依赖和独立固定测试依赖。
- `tests/conftest.py`、`tests/backend/test_*.py`、`scripts/probe_sse_concurrency.py`：原有与新增离线回归、真实 loopback 时序探针。
- `.github/workflows/backend-regression.yml`、`.gitignore`、README、本文、MENTORING 与 evidence：CI、复现与能力证据。
- `bench/code_assistant/*`：后续实验的固定任务、独立用例、可信快照自检和工作目录准备工具；不接入生产服务。

所有变更保留在独立分支工作区，未覆盖旧 F 盘作品或 G 盘目录。2026-10-20 已推送到 `agent/reliability-20261020` 并创建 [PR #1](https://github.com/1391363774-lgtm/ai-digital-human-tour-guide/pull/1)，尚未合并 master。PR 的 Files changed 可同时审阅生产逻辑、测试、文档与 CI。

测试命令、原始摘要、基准 SHA 与最终时序见 `evidence/reliability/execution.json`。原始本机 pytest 日志和 JUnit 留在同目录并被 gitignore 排除，避免公开工作站绝对路径；时间线与摘要不含真实游客数据/模型 Key。

未验收：真实云模型连通性、生产负载、PostgreSQL 下的迁移/并发、物理 Chroma 清理、浏览器/语音端端到端、100 题重新评测。本次没有生成新的问答准确率，也没有宣称通过所有部署方式。

网络读超时不等于首有效文本的总体截止时间；如果上游不断发送心跳但不结束，仍需要后续加入总时限。本次只修复“正常结束但没有有效文本”与明确异常的备用行为。

后续独立任务材料见 [最小代码助手实验](../bench/code_assistant/README.md)：20个固定可信故障快照、12开发/8验收、60个独立用例。快照自检全部确认原始缺陷可触发；Prompt与工具反馈方案尚未运行，不把该自检当Agent成功率。
