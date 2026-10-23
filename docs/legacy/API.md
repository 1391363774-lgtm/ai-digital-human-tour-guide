# API 文档

## 统一响应

```json
{"code": 200, "message": "success", "data": {}}
```

## 基础接口

### GET /health

用于健康检查。

响应：

```json
{"code": 200, "message": "success", "data": {"status": "ok"}}
```

## 主要接口

| 模块 | 方法 | 路径 | 说明 |
|---|---|---|---|
| Scenic | GET | `/api/spots` | 游客侧景点列表 |
| Scenic | POST | `/api/admin/spots` | 新增景点 |
| Scenic | PUT | `/api/admin/spots/{spot_id}` | 更新景点 |
| Scenic | DELETE | `/api/admin/spots/{spot_id}` | 删除景点 |
| Knowledge | POST | `/api/admin/knowledge/upload` | 上传知识文档 |
| Knowledge | GET | `/api/admin/knowledge` | 知识文档列表 |
| Knowledge | GET | `/api/admin/knowledge/{document_id}/parse-preview` | 文档解析预览 |
| Knowledge | POST | `/api/admin/knowledge/{document_id}/chunks` | 构建知识块 |
| Knowledge | POST | `/api/admin/knowledge/{document_id}/index` | 构建向量索引 |
| RAG | POST | `/api/rag/search` | RAG 检索 |
| Chat | POST | `/api/chat/messages` | 文本问答与会话持久化 |
| Chat | POST | `/api/chat/stream` | SSE 增量问答；已开始输出后不会跨模型拼接 |
| History | GET | `/api/history` | 会话列表 |
| History | GET | `/api/history/{conversation_id}` | 会话详情 |
| Routes | POST | `/api/routes/recommend` | 个性化路线推荐 |
| Speech | POST | `/api/speech/asr` | 语音转文本 |
| Speech | POST | `/api/speech/tts` | 文本转 MP3 音频流，默认 edge-tts Xiaoxiao 女声 |
| Speech | POST | `/api/speech/tts/segments` | 分段并行合成，返回文本段与 Base64 MP3 |
| Speech | POST | `/api/speech/tts/stream` | NDJSON 分段语音流，首段优先返回 |
| Multimodal | POST | `/api/multimodal/image-question` | Qwen-VL 拍照识景（需配置 Qwen Key） |
| Favorite | POST | `/api/favorites` | 添加收藏 |
| Favorite | GET | `/api/favorites` | 收藏列表 |
| Favorite | DELETE | `/api/favorites/{favorite_id}` | 删除收藏 |
| Feedback | POST | `/api/feedback` | 提交游客反馈 |
| Feedback | POST | `/api/feedback/analyze` | 单条反馈情绪分析 |
| Feedback | GET | `/api/feedback/stats` | 满意度与待关注反馈统计 |
| Behavior | POST | `/api/behavior/events` | 记录游客行为事件 |
| Behavior | POST | `/api/behavior/import` | CSV 导入游客行为数据 |
| Behavior | GET | `/api/behavior/stats` | 行为事件统计 |
| Dashboard | GET | `/api/dashboard/overview` | 运营数据大屏总览 |

## 冒烟测试

服务启动后执行：

```powershell
python scripts/smoke_test.py --base-url http://localhost:8000
```
