# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for 景区导览AI数字人"""
import os
from pathlib import Path

# spec 文件所在目录 = 项目根目录
SPEC_DIR = Path(SPECPATH).resolve()
BACKEND_DIR = SPEC_DIR / 'backend'
FRONTEND_DIST = SPEC_DIR / 'frontend' / 'dist'
FRONTEND_PUBLIC = SPEC_DIR / 'frontend' / 'public'
DATA_DIR = SPEC_DIR / 'data'
AI_DIR = SPEC_DIR / 'ai'

datas = []

# ── 前端构建产物 ──
if FRONTEND_DIST.is_dir():
    datas.append((str(FRONTEND_DIST), 'frontend/dist'))

# ── Live2D 模型文件 ──
models_dir = FRONTEND_PUBLIC / 'models'
if models_dir.is_dir():
    datas.append((str(models_dir), 'frontend/public/models'))

# ── 前端 public 下其他资源（avatars, maps 等）──
public_assets = FRONTEND_PUBLIC / 'assets'
if public_assets.is_dir():
    datas.append((str(public_assets), 'frontend/public/assets'))

# ── avatar-config.json ──
avatar_config = FRONTEND_PUBLIC / 'avatar-config.json'
if avatar_config.is_file():
    datas.append((str(avatar_config), 'frontend/public'))

# ── AI prompts ──
prompts_dir = AI_DIR / 'prompts'
if prompts_dir.is_dir():
    datas.append((str(prompts_dir), 'ai/prompts'))

# ── 向量库（chroma）──
vector_store = DATA_DIR / 'vector_store'
if vector_store.is_dir():
    datas.append((str(vector_store), 'data/vector_store'))

# ── SQLite 数据库（打包后使用，无需 PostgreSQL）──
sqlite_db = DATA_DIR / 'app.db'
if sqlite_db.is_file():
    datas.append((str(sqlite_db), 'data'))

# ── .env 配置文件（API 密钥等）──
env_file = BACKEND_DIR / '.env'
if env_file.is_file():
    datas.append((str(env_file), '.'))

hiddenimports = [
    # uvicorn
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    # FastAPI / Starlette
    'multipart',
    'anyio._backends._asyncio',
    'starlette',
    'starlette.routing',
    'starlette.middleware',
    'starlette.responses',
    'starlette.staticfiles',
    # SQLAlchemy
    'sqlalchemy',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.sql.default_comparator',
    # Alembic
    'alembic',
    'alembic.migration',
    'alembic.config',
    'alembic.script',
    # ChromaDB
    'chromadb',
    'chromadb.api',
    'chromadb.api.local',
    'chromadb.config',
    'chromadb.db',
    'chromadb.db.impl',
    'chromadb.db.impl.sqlite',
    'chromadb.utils',
    'chromadb.utils.embedding_functions',
    'chromadb.types',
    'chromadb.telemetry',
    # TTS
    'edge_tts',
    # ASR
    'faster_whisper',
    # Pydantic
    'pydantic',
    'pydantic_settings',
    'pydantic.fields',
    # HTTP
    'httpx',
    'h11',
    # Image / Math
    'numpy',
    'PIL',
    'PIL._tkinter_finder',
    # LLM
    'openai',
    # ONNX Runtime (chromadb / faster_whisper)
    'onnxruntime',
    # Database drivers
    'psycopg',
    'psycopg._psycopg',
]

a = Analysis(
    [str(BACKEND_DIR / 'launch.py')],
    pathex=[str(BACKEND_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'tkinter', 'scipy', 'pandas',
        'IPython', 'jupyter', 'notebook', 'pytest',
        'torch', 'tensorflow', 'transformers',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='景区导览AI数字人',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='景区导览AI数字人',
)
