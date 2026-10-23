# 2026-10-23 工程交付与验证边界

## 基准和视觉纠正

后续只使用 `guide-live2d-20261023` 工作区，来源由用户明确确认为 `21018015作品/灵山胜境AI数字人/`。原目录只读，未执行原 exe/launcher/build_exe。最初误选的 `21018015源码` 工作区没有推送，也未进入本分支历史；关于其占位后端的结论已撤回作为本版判断。

本版保留用户截图的侧栏、首页轮播、金/蓝色样式、Natori 男性 Live2D、形象/表情按钮及桌宠。首页窄窗会响应式排列。未默认改成 SVG 或照片；后备行为仍按原资源失败条件触发。新增停止按钮、引用展开和明确的演示/服务配置状态；口型文案改为估算，未改变默认模型。

## 独立提交

- `1ef2dfd`：正确运行版脱敏基线，实际无 Key 启动，原两项 fallback 测试通过。
- `865685f`：先复现 4 项协议失败，再修复白流、断流/异常结束和禁止半途拼接，8 项模型回归通过。
- `a831127`：先复现 5 项无鉴权访问，再绑定游客 capability、管理密钥、本人评价、短期音频授权与前端同源接线，17 项累计回归通过。
- `e8476a8`：先复现新增知识检索不到、修改后仍旧内容、embedding 身份不进入缓存 3 项失败，再原子发布完整 RAG 快照；24 项累计通过。
- `6711631`：先复现短回答 delta 丢失、异常细节泄露、无依据仍调用模型 3 项失败，再加入有界 TTS、请求终态、取消清理和离线合成测试音。后续 UI/CI/验收提交见 Git 历史。

这些是 AI 编程助手本轮新增或迁移的工作，不能直接记成团队成员独立贡献。原项目已有异步 httpx SSE、初版 fallback、TF-IDF/embedding、edge-tts/拼音估算、SQLite 和 Live2D 界面。

## 本地实际执行

- 旧版：106 后端、17 前端测试通过。旧构建在受限 Windows 文件复制阶段未成功，未计为构建通过。
- 新版：`python -m pytest tests/backend -q -p no:cacheprovider --junitxml=test-results/backend.xml --basetemp <可写目录>`，**38 passed**。覆盖协议、访问边界、知识 CRUD/重分块/回滚/跨进程提交、CPU 工作让出事件循环、取消持久化、TTS 去重/并发/关闭和真实 loopback SSE。
- `cd frontend; npm test -- --reporter=dot`，**11 passed**。覆盖增量 UTF-8/CRLF、无终态/坏帧、请求 ID 混流、reader 清理、队列有界/去重、新问取消旧流、真实页面按钮绑定、播放器停止及同源凭据限制。
- `npm run build` 成功：TypeScript 共享运行时类型检查、15 个 HTML 页、27 段脚本语法检查；不是 Vue 全工程类型检查。原生页面本身仍是 JavaScript。
- Windows Node 原生 `cpSync` 在本机异常退出；改用明确目录中的逐文件读写后成功，构建不执行原项目脚本。
- `python scripts/run_demo.py --port 8083` 实际启动，浏览器看到原 Natori。提问“灵山大佛有多高”后有摘录、来源、completed，播放队列归零；实际点停止后仍保留文字，口部复位。截图保存在本地私有交付目录，不含私人数据，不提交。
- `python scripts/smoke_demo.py --base-url http://127.0.0.1:8083` 成功：TF-IDF → SSE → 来源 → 合成 WAV 取回 → 完成持久化 → 两游客隔离。它在非演示模式会拒绝发问题。
- 真实 socket 回归：在慢速模型替身流动时健康检查可响应；连接断开关闭上游生成器，数据库记录 cancelled。此测试不代表真实供应商性能或生产并发指标。
- `docker compose config --quiet` 返回 0，本机 Docker 配置目录有权限警告；本地未构建镜像或启动容器。GitHub Actions 将构建镜像并在 runner 的 loopback 做演示冒烟，不公开部署。

## 运行与新增工程依赖

Python 3.13，Node 24。`backend/requirements-lock.txt` 是本轮实际安装版本（含测试依赖）；`frontend/package-lock.json` 为锁定 npm 依赖。后端应用技术沿用新源码，新增工程工具为 TypeScript/Vitest/jsdom、Lucide/ECharts 本地构建；没有下载 AI 权重。

演示启动见 README；`DEMO_MODE=true` 关闭云模型和 embedding，音频是 250 ms 合成测试音，不是自然语音。默认管理未配置为 503；可在本地进程环境显式设置 ADMIN_API_KEY，不输出、不写入前端或公开文件。

真实模式需自行配置 LLM_*、可选 LLM_FALLBACK_*、ADMIN_API_KEY 等，且会有在线模型/embedding/edge-tts 行为。本轮未替用户启用、购买或调用。不要用 VITE_* 存放秘密。

## 尚未验证与合并条件

- 真实 Qwen/备用供应商/embedding/edge-tts、麦克风 ASR、拍照识景、扫码在真实设备上的行为，均只到实现/接线或替身验证；没有真实外部服务验收。
- 100 题数据保留，未执行完整评分；没有准确率、上线、用户量、吞吐量、首字/首音频优化比例等指标。
- TF-IDF 是词法检索；有 Key 的 embedding 路径未实测。引用显示提供的资料片段，不保证外部事实/时效内容正确。旧版 Chroma/Milvus/Redis 不能作为本版已接通技术写进简历。
- 当前默认单 worker。短期音频授权和 TTS 并发状态在内存中，多 worker/多实例需共享授权与限流；本轮只验证 SQLite 跨进程知识版本刷新，未宣称分布式可靠性。
- capability 是持有者凭据，受同源脚本安全影响，不是完整账号/RBAC 系统。清理浏览器存储会失去对应会话入口。
- SQLite 使用加表/加列升级；不导入旧项目私有数据库，不提供旧 PostgreSQL/Chroma 数据迁移。MySQL、旧 exe 打包和硬件 GPS 行为未验证。
- 资产、Cubism Core、样例模型和知识文本的来源/发布权利待团队补齐。此事项需要人工审核，因此 PR 保持草稿，不合并；默认分支未包含本轮提交之前，不能称“替换完成”。

## 删除与恢复

逐文件清单见 old-file-disposition.csv；有效的通用模型/SSE/访问/新鲜性/音频契约已适配到新接口，未宣称旧 106 个测试原样全部迁入。原 Vue 独有页面/API、旧数据库/索引迁移、旧部署与部分评测脚本退出活动树；公共资料和评测数据保留，历史文档在 docs/legacy。

恢复分支：`backup/pre-new-source-20261023` → `8f2b0d289fb969ae36bd14e0100ed5f219e94513`。不强推、不重置他人工作、不删除历史。原 .env、私人运行数据和原始游客分析未导入；曾共享或暴露的凭据应由持有人撤销/轮换，删除副本不能撤销凭据。
