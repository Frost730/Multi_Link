"""
MultiLink Automated Desktop Build Script
Compiles frontend, resolves dependencies, and runs PyInstaller to build MultiLink.exe.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"


def check_prerequisites():
    print("==> Checking prerequisites...")
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("ERROR: PyInstaller is not installed. Run: pip install pyinstaller")
        sys.exit(1)


def build_frontend():
    print("\n==> Building frontend...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    result = subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)
    if result.returncode != 0:
        print("ERROR: Frontend build failed.")
        sys.exit(result.returncode)

    frontend_dist = FRONTEND_DIR / "dist"
    if not (frontend_dist / "index.html").exists():
        print(f"ERROR: Expected {frontend_dist / 'index.html'} does not exist!")
        sys.exit(1)
    print("Frontend build succeeded.")


def build_executable():
    print("\n==> Running PyInstaller...")
    frontend_dist = FRONTEND_DIR / "dist"
    backend_dir = ROOT_DIR / "backend"

    # Assemble PyInstaller command
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=MultiLink",
        "--onedir",  # onedir builds much faster and launches instantly
        "--windowed", # no black console window
        "--noconfirm",
        f"--paths={backend_dir}",
        f"--add-data={frontend_dist}{sep}dist",
        f"--add-data={backend_dir / 'app'}{sep}backend/app",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=aiosqlite",
        "--hidden-import=sqlite3",
        "--hidden-import=aiohttp",
        "--hidden-import=psutil",
        "--hidden-import=pydantic",
        "--hidden-import=fastapi",
        "--hidden-import=starlette",
        str(ROOT_DIR / "launcher.py")
    ]

    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        print("ERROR: PyInstaller packaging failed.")
        sys.exit(result.returncode)

    exe_path = DIST_DIR / "MultiLink" / "MultiLink.exe"
    if exe_path.exists():
        print(f"\n[SUCCESS] Desktop application built successfully at:\n  {exe_path}")
    else:
        print("\n[WARNING] Build finished but executable path could not be confirmed.")


def main():
    check_prerequisites()
    build_frontend()
    build_executable()


if __name__ == "__main__":
    main()
