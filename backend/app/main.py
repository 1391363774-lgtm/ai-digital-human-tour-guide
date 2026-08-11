from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import chat, knowledge, avatar, analytics

app = FastAPI(title="灵山胜境AI数字人导览系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(avatar.router, prefix="/api/avatar", tags=["数字人"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "灵山胜境AI数字人"}
