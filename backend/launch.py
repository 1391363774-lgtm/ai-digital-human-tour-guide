"""
景区导览服务 AI 数字人 - 启动入口
双击运行即可启动后端 API 服务和前端页面，自动打开浏览器。
"""
import os
import sys
import webbrowser
import threading
import time
from pathlib import Path

# 兼容 PyInstaller 打包后的路径
if getattr(sys, 'frozen', False):
    # PyInstaller 打包后：exe 在根目录，依赖在 _internal/
    BASE_DIR = Path(sys.executable).resolve().parent
    INTERNAL_DIR = BASE_DIR / "_internal"
    sys.path.insert(0, str(INTERNAL_DIR))
else:
    # 开发模式：launch.py 在 backend/ 下，项目根目录是上一级
    BASE_DIR = Path(__file__).resolve().parent.parent
    INTERNAL_DIR = BASE_DIR

# 设置工作目录为项目根目录（数据库等相对路径依赖此目录）
os.chdir(str(BASE_DIR))

# 确保关键环境变量指向正确目录
DATA_DIR = INTERNAL_DIR / "data"
FRONTEND_DIST_DIR = INTERNAL_DIR / "frontend" / "dist"
FRONTEND_MODELS_DIR = INTERNAL_DIR / "frontend" / "public" / "models"
AI_PROMPTS_DIR = INTERNAL_DIR / "ai" / "prompts"

os.environ.setdefault("CHROMA_PERSIST_DIR", str(DATA_DIR / "vector_store" / "chroma"))
os.environ.setdefault("KNOWLEDGE_RAW_DIR", str(DATA_DIR / "raw"))
os.environ.setdefault("APP_ENV", "production")

# 打包后默认使用 SQLite（接收方无需安装 PostgreSQL）
if getattr(sys, 'frozen', False):
    SQLITE_PATH = DATA_DIR / "app.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{SQLITE_PATH}")

# 加载 .env 文件（如果存在）
ENV_FILE = BASE_DIR / ".env"
if not ENV_FILE.is_file():
    ENV_FILE = INTERNAL_DIR / ".env"
if not ENV_FILE.is_file():
    # 开发模式下 .env 可能在 backend/ 目录
    ENV_FILE = Path(__file__).resolve().parent / ".env"
if ENV_FILE.is_file():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and value and key not in os.environ:
                os.environ[key] = value

# 确保 ai/prompts 目录可被 prompt_service 找到
if AI_PROMPTS_DIR.is_dir():
    os.environ.setdefault("PROMPT_TEMPLATE_DIR", str(AI_PROMPTS_DIR))


def _ensure_sqlite_tables():
    """打包后若 SQLite 数据库文件不存在，自动创建表结构。"""
    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url.startswith("sqlite"):
        return
    # 从 DATABASE_URL 提取文件路径
    db_file_str = db_url.replace("sqlite:///", "", 1)
    db_file = Path(db_file_str)
    if db_file.is_file():
        return  # 数据库文件已存在，跳过
    print(f"[初始化] SQLite 数据库不存在，正在创建: {db_file}")
    db_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        from app.core.database import Base, engine
        # 导入所有模型以确保表全部创建
        from app.models import (  # noqa: F401
            avatar, conversation, favorite, feedback, knowledge,
            recommendation, scenic, system_log, user, visitor_event,
        )
        Base.metadata.create_all(bind=engine)
        print(f"[初始化] SQLite 表结构创建完成")
    except Exception as e:
        print(f"[警告] SQLite 初始化失败: {e}")


_ensure_sqlite_tables()

import uvicorn


def serve_frontend():
    """在 5174 端口提供前端静态文件服务"""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    static_app = FastAPI()
    dist_path = FRONTEND_DIST_DIR
    if dist_path.is_dir():
        assets_path = dist_path / "assets"
        if assets_path.is_dir():
            static_app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")
        # Live2D 模型
        if FRONTEND_MODELS_DIR.is_dir():
            static_app.mount("/models", StaticFiles(directory=str(FRONTEND_MODELS_DIR)), name="models")
        # 其他 public 子目录
        public_dir = FRONTEND_DIST_DIR.parent / "public"
        if not public_dir.is_dir():
            public_dir = dist_path.parent / "public"
        if public_dir.is_dir():
            for item in public_dir.iterdir():
                if item.is_dir() and item.name not in ("models", "assets"):
                    try:
                        static_app.mount(f"/{item.name}", StaticFiles(directory=str(item)), name=f"static_{item.name}")
                    except Exception:
                        pass

        @static_app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            file = dist_path / full_path
            if file.is_file():
                return FileResponse(str(file))
            return FileResponse(str(dist_path / "index.html"))

        uvicorn.run(static_app, host="127.0.0.1", port=5174, log_level="warning")
    else:
        print(f"[警告] 前端文件未找到: {dist_path}")


def open_browser():
    """延迟 2 秒后自动打开浏览器"""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:5174/")


def main():
    print("=" * 50)
    print("  景区导览服务 AI 数字人")
    print("  正在启动服务...")
    print("=" * 50)
    print(f"  根目录: {BASE_DIR}")
    print(f"  内部目录: {INTERNAL_DIR}")
    print(f"  前端目录: {FRONTEND_DIST_DIR}")
    print(f"  数据目录: {DATA_DIR}")
    print("=" * 50)

    # 在后台线程启动前端静态服务
    frontend_thread = threading.Thread(target=serve_frontend, daemon=True)
    frontend_thread.start()

    # 延迟打开浏览器
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print("  前端地址: http://127.0.0.1:5174/")
    print("  后端地址: http://127.0.0.1:8000/")
    print("  按 Ctrl+C 停止服务")
    print("=" * 50)

    # 导入 app（让 PyInstaller 静态分析能追踪 app 包）
    from app.main import app as backend_app

    # 主线程运行后端 API 服务
    uvicorn.run(
        backend_app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()