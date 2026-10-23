"""
灵山胜境AI数字人导览系统 - 一体化启动器
================================================
双击运行(或 python launcher.py):
  1. 启动 FastAPI 后端(大模型+RAG+TTS+口型时间轴)
  2. 托管前端页面(游客端+管理后台)
  3. 自动打开浏览器进入系统

评委体验: 零依赖、零配置、双击即用。
打包exe: 见 build_exe.py(PyInstaller)
"""
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

PORT = 8080


def get_base_dir() -> Path:
    """定位项目根目录(兼容源码运行与PyInstaller打包)"""
    if getattr(sys, "frozen", False):
        # PyInstaller: exe位于项目根目录
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main():
    base_dir = get_base_dir()
    backend_dir = base_dir / "backend"
    os.chdir(backend_dir)
    sys.path.insert(0, str(backend_dir))

    # PyInstaller冻结环境下,数据目录放到exe同级(可写)
    if getattr(sys, "frozen", False):
        data_dir = base_dir / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print("   灵山胜境 AI数字人导览系统  v2.0")
    print("   第十五届中国软件杯 A5赛题参赛作品")
    print("=" * 56)
    print()
    print("  [1/3] 正在启动AI服务(首次启动需构建知识库索引)...")

    import uvicorn
    # 直接导入app对象(而非字符串路径):
    # 1) PyInstaller可静态追踪完整依赖图,确保fastapi等全部打包
    # 2) 避免冻结环境下模块解析问题
    from app.main import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=PORT,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    def run_server():
        import asyncio
        asyncio.run(server.serve())

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # 等待服务就绪
    import urllib.request
    for i in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
            break
        except Exception:
            time.sleep(1)

    print(f"  [2/3] 服务已就绪: http://127.0.0.1:{PORT}")
    print("  [3/3] 正在打开浏览器...")
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print(f"  │  游客端:   http://127.0.0.1:{PORT}/pages/home.html   │")
    print(f"  │  数字人导览: http://127.0.0.1:{PORT}/pages/guide.html  │")
    print(f"  │  管理后台: http://127.0.0.1:{PORT}/pages/admin.html  │")
    print("  └─────────────────────────────────────────────┘")
    print()
    print("  关闭本窗口即停止系统。")
    print("=" * 56)

    webbrowser.open(f"http://127.0.0.1:{PORT}/pages/home.html")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  系统已停止,再见!")


if __name__ == "__main__":
    main()
