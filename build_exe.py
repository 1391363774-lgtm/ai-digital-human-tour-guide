"""
PyInstaller 打包脚本 - 生成单文件exe(评委双击即用)
用法: python build_exe.py
产物: dist/灵山胜境AI数字人.exe (放入项目根目录后双击运行)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

CMD = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--name", "灵山胜境AI数字人",
    "--icon", "NONE",
    # 工作入口
    str(ROOT / "launcher.py"),
    # 路径搜索
    "--paths", str(ROOT / "backend"),
    # 隐式依赖(PyInstaller静态分析可能遗漏)
    "--hidden-import", "uvicorn.logging",
    "--hidden-import", "uvicorn.loops.auto",
    "--hidden-import", "uvicorn.protocols.http.auto",
    "--hidden-import", "uvicorn.protocols.websockets.auto",
    "--hidden-import", "uvicorn.lifespan.on",
    "--hidden-import", "edge_tts",
    "--hidden-import", "pypinyin",
    "--hidden-import", "jieba",
    "--hidden-import", "aiosqlite",
    "--hidden-import", "sqlalchemy.dialects.sqlite.aiosqlite",
    "--hidden-import", "numpy",
    "--hidden-import", "httpx",
    # jieba词典数据
    "--collect-data", "jieba",
    "--collect-data", "pypinyin",
]

if __name__ == "__main__":
    print("开始打包(约2-5分钟)...")
    print(" ".join(CMD))
    subprocess.run(CMD, check=True, cwd=ROOT)
    print()
    print("=" * 56)
    print("打包完成! 产物: dist/灵山胜境AI数字人.exe")
    print()
    print("部署方式: 将exe复制到项目根目录(与 backend/ design/ 知识库/ 同级),")
    print("          双击即可运行。backend/.env 中的API Key会在运行时读取。")
    print("=" * 56)
