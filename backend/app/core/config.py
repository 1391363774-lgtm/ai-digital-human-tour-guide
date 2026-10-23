"""
灵山胜境AI数字人导览系统 - 全局配置
所有配置均可通过 backend/.env 覆盖,开箱即用、无Key自动降级。
"""
import sys
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# 项目根目录(灵山胜境AI数字人/)
if getattr(sys, "frozen", False):
    # PyInstaller打包:exe位于项目根目录
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # 源码运行:config.py → core → app → backend → 项目根,共向上4级
    BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"


class Settings(BaseSettings):
    APP_NAME: str = "灵山胜境AI数字人导览系统"
    ADMIN_API_KEY: str = ''
    DEMO_MODE: bool = False
    CORS_ORIGINS: str = 'http://127.0.0.1:8080,http://localhost:8080'

    # ---- LLM(兼容OpenAI接口:DashScope/DeepSeek/智谱/Kimi均可) ----
    # 现有 LLM_* 作为 primary，保留原变量名以兼容已有 .env。
    # 当 primary 在首个有效 token 前失败时，才会尝试 LLM_FALLBACK_*。
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode"
    LLM_MODEL: str = "qwen-plus"          # 对话生成(快)
    LLM_TIMEOUT: float = 30.0
    LLM_FALLBACK_API_KEY: str = ""
    LLM_FALLBACK_BASE_URL: str = ""
    LLM_FALLBACK_MODEL: str = ""
    LLM_FALLBACK_TIMEOUT: float = 30.0
    # 仅用于本地验证，不要在生产环境设置。可选: primary_timeout / primary_error
    # fallback_timeout / fallback_error
    LLM_FAULT_INJECT: str = ""
    VLM_MODEL: str = "qwen-vl-max"        # primary 多模态图像理解模型
    VLM_FALLBACK_MODEL: str = ""          # fallback 多模态模型；留空则视觉接口不切换

    # ---- Embedding(知识库向量化;无Key时自动降级TF-IDF) ----
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024

    # ---- ASR语音识别 ----
    ASR_MODEL: str = "paraformer-zh"

    # ---- TTS语音合成(edge-tts 神经网络音色) ----
    TTS_MODEL: str = "cosyvoice-v1"           # 文档兼容保留
    TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"   # 晓晓·温柔女声
    TTS_VOICE_ALT: str = "zh-CN-XiaoyiNeural"  # 备选音色
    TTS_RATE: str = "+0%"
    TTS_PITCH: str = "+0Hz"

    # ---- 数据库(默认SQLite,exe双击即跑;MySQL可选) ----
    DATABASE_URL: str = f"sqlite+aiosqlite:///{BACKEND_DIR / 'data' / 'lingshan.db'}"
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DATABASE: str = "lingshan_guide"

    # ---- 缓存/向量库(可选扩展,默认本地numpy向量文件) ----
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "lingshan_knowledge"

    # ---- 路径 ----
    KNOWLEDGE_MD: str = str(BASE_DIR / "知识库" / "灵山胜境完整知识库.md")
    FRONTEND_DIR: str = str(BASE_DIR / "design" / "lingshan-guide")
    ADMIN_DIR: str = str(BASE_DIR / "design" / "lingshan-admin")
    VECTOR_CACHE: str = str(BACKEND_DIR / "data" / "knowledge_vectors.npz")
    TTS_CACHE_DIR: str = str(BACKEND_DIR / "data" / "tts_cache")

    # ---- 检索参数 ----
    RAG_TOP_K: int = 4
    RAG_SCORE_THRESHOLD: float = 0.15

    class Config:
        env_file = str(BACKEND_DIR / ".env")
        extra = "ignore"


settings = Settings(_env_file=None) if os.environ.get('GUIDE_NO_ENV_FILE') == '1' else Settings()
if settings.DEMO_MODE:
    settings.LLM_API_KEY = ''
    settings.LLM_FALLBACK_API_KEY = ''

# 确保数据目录存在
(BACKEND_DIR / "data").mkdir(parents=True, exist_ok=True)
Path(settings.TTS_CACHE_DIR).mkdir(parents=True, exist_ok=True)
