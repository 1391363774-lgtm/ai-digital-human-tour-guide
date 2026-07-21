# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

PROJECT_DIR = r'F:\软件杯AI数字人'
BACKEND_DIR = os.path.join(PROJECT_DIR, 'backend')
FRONTEND_DIST = os.path.join(PROJECT_DIR, 'frontend', 'dist')
FRONTEND_PUBLIC = os.path.join(PROJECT_DIR, 'frontend', 'public')
DATA_DIR = os.path.join(PROJECT_DIR, 'data')

# 收集前端 dist 所有文件
datas = [
    (FRONTEND_DIST, 'frontend/dist'),
    (os.path.join(FRONTEND_PUBLIC, 'models'), 'frontend/public/models'),
    (os.path.join(PROJECT_DIR, 'ai', 'prompts'), 'ai/prompts'),
    (os.path.join(DATA_DIR, 'vector_store'), 'data/vector_store'),
    (os.path.join(DATA_DIR, 'raw'), 'data/raw'),
    (os.path.join(DATA_DIR, 'eval'), 'data/eval'),
    (os.path.join(DATA_DIR, 'processed'), 'data/processed'),
    (os.path.join(BACKEND_DIR, '.env'), '.'),
]

# 收集后端所有 Python 包
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'multipart',
    'anyio._backends._asyncio',
    'sqlalchemy',
    'alembic',
    'chromadb',
    'edge_tts',
    'faster_whisper',
    'pydantic',
    'pydantic_settings',
    'httpx',
    'numpy',
    'PIL',
    'openai',
]

a = Analysis(
    [os.path.join(BACKEND_DIR, 'launch.py')],
    pathex=[BACKEND_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'tkinter', 'scipy', 'pandas',
        'IPython', 'jupyter', 'notebook',
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
    console=True,  # 保留控制台窗口以便看日志
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