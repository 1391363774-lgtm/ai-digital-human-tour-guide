from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.behavior import router as behavior_router
from app.api.routes.avatar_config import router as avatar_config_router
from app.api.routes.chat import router as chat_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.favorite import router as favorite_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.history import router as history_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.multimodal import router as multimodal_router
from app.api.routes.rag import router as rag_router
from app.api.routes.route import router as route_router
from app.api.routes.scenic import router as scenic_router
from app.api.routes.speech import router as speech_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.response import success

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return success({"status": "ok", "env": settings.app_env})


app.include_router(knowledge_router)
app.include_router(multimodal_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(route_router)
app.include_router(speech_router)
app.include_router(scenic_router)
app.include_router(favorite_router)
app.include_router(feedback_router)
app.include_router(behavior_router)
app.include_router(dashboard_router)
app.include_router(avatar_config_router)
