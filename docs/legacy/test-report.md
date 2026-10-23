# 测试报告

## 当前验证结论

| 项目 | 结果 | 说明 |
|---|---|---|
| 后端编译 | 通过 | `python -m compileall backend/app` 多次通过 |
| Alembic 脚本编译 | 通过 | `backend/alembic` 编译通过 |
| 官方景点资料 dry-run | 通过 | 本地官方资料包解析出 16 条景点记录 |
| 前端源配置 | 通过 | 已补齐 `index.html`、`tsconfig.json`、`tsconfig.node.json`、`env.d.ts` |
| Docker Compose 配置 | 通过 | `docker compose config` 通过 |
| Docker 镜像构建 | 未执行 | Docker Desktop Linux Engine 未运行 |
| npm 构建 | 未执行 | `npm install` 在当前环境静默挂起 |
| pip 依赖安装 | 未执行 | 当前代理拒绝访问 Python 包索引 |

## 问答准确率

| 日期 | 问题数 | 准确数 | 准确率 |
|---|---:|---:|---:|
| 待运行 | 100 | - | - |

评测命令：

```powershell
python scripts/eval_qa_accuracy.py --base-url http://localhost:8000
```

评测集：`data/eval/qa_testset.json`。

## 延迟测试

| 日期 | 场景 | 平均耗时 | P95 |
|---|---|---:|---:|
| 待运行 | `/api/chat/messages` | - | - |

延迟测试脚本：`scripts/benchmark_latency.py`。

## 冒烟测试

服务启动后执行：

```powershell
python scripts/smoke_test.py --base-url http://localhost:8000
```

覆盖接口：

- `/health`
- `/api/spots`
- `/api/chat/messages`
- `/api/routes/recommend`
- `/api/feedback/stats`
- `/api/dashboard/overview`
