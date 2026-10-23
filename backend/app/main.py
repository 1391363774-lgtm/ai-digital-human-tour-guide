"""
灵山胜境AI数字人导览系统 - FastAPI 主入口
单进程一体化:API服务 + 前端静态托管 + 启动即构建知识库
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse,JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import chat, knowledge, avatar, analytics, tts
from app.core.config import settings
from app.core.access import admin_route,require_admin,visitor_owner
from app.core.database import init_db
from app.services.rag_service import rag_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动:建表 + 构建知识库(向量/TF-IDF)
    await init_db()
    try:
        await rag_service.build()
    except Exception as e:
        print(f"[启动] 知识库构建失败(降级继续运行): {e}")
    yield


app = FastAPI(title="灵山胜境AI数字人导览系统", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.CORS_ORIGINS.split(',') if x.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware('http')
async def access_boundary(request,call_next):
    path=request.url.path.rstrip('/')
    try:
        if request.method != 'OPTIONS':
            if admin_route(path,request.method):
                require_admin(request.headers.get('X-Admin-Key'))
            elif path.startswith(('/api/chat/history','/api/chat/send','/api/chat/stream','/api/chat/vision')) or path.startswith('/api/tts') and not path.startswith('/api/tts/audio/') or path in ('/api/analytics/rate','/api/analytics/checkin','/api/analytics/my-visits'):
                visitor_owner(request.headers.get('X-Visitor-Key'))
        return await call_next(request)
    except HTTPException as exc:
        return JSONResponse({'detail':exc.detail},status_code=exc.status_code)

app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(tts.router, prefix="/api/tts", tags=["语音合成"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(avatar.router, prefix="/api/avatar", tags=["数字人"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["数据分析"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME, "rag": rag_service.status}


@app.get("/api/status")
async def system_status():
    from app.services.llm_service import llm_service
    return {
        'demo_mode':settings.DEMO_MODE,
        "llm_available": llm_service.available,
        "llm_model": settings.LLM_MODEL,
        "llm": llm_service.status,
        "rag": rag_service.status,
        "tts_voice": settings.TTS_VOICE,
    }


# ---------------- 静态托管(游客端 + 管理后台) ----------------
frontend_dir = Path(settings.FRONTEND_DIR)
admin_dir = Path(settings.ADMIN_DIR)

if admin_dir.exists():
    app.mount("/admin", StaticFiles(directory=str(admin_dir), html=True), name="admin")


@app.get("/")
async def root():
    return RedirectResponse(url="/pages/home.html")


if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
