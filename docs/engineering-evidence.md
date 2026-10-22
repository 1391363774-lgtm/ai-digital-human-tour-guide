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
