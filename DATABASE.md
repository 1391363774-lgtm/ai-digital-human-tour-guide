# 数据库设计

## ER 关系

```text
User 1 ── N Conversation
Conversation 1 ── N Message
User 1 ── N Favorite
ScenicSpot 1 ── N Favorite
ScenicSpot 1 ── N RecommendationItem
Recommendation 1 ── N RecommendationItem
KnowledgeDocument 1 ── N KnowledgeChunk
User 1 ── N Feedback
Conversation 1 ── N Feedback
AvatarConfig 记录数字人形象、声音和风格
SystemLog 记录系统事件、异常和性能数据
```

## 核心表

| 表 | 说明 |
|---|---|
| users | 游客与管理员 |
| scenic_spots | 景点结构化数据 |
| knowledge_documents | 知识文档 |
| knowledge_chunks | 文档分块与向量映射 |
| conversations | 会话 |
| messages | 消息 |
| recommendations | 路线推荐 |
| recommendation_items | 路线景点明细 |
| favorites | 收藏 |
| feedback | 游客反馈 |
| avatar_configs | 数字人配置 |
| system_logs | 系统日志 |

## 迁移记录

| 版本 | 日期 | 变更 |
|---|---|---|
| 0001 | 初始化 | 创建核心业务表 |
