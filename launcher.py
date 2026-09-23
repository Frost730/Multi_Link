"""
MultiLink Desktop Application Launcher
Runs FastAPI backend with embedded React UI and launches native borderless app window.
"""
import os
import sys
import time
import socket
import shutil
import logging
import threading
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

# Configure paths
ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

if BACKEND_DIR.exists() and str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    meipass = Path(sys._MEIPASS)
    if (meipass / "backend").exists() and str(meipass / "backend") not in sys.path:
        sys.path.insert(0, str(meipass / "backend"))
    if str(meipass) not in sys.path:
        sys.path.insert(0, str(meipass))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MultiLink.Launcher")


def find_free_port(preferred: int = 8000) -> int:
    """Check if preferred port is free, otherwise find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get_browser_executable() -> str | None:
    """Find Microsoft Edge or Google Chrome for --app borderless mode."""
    candidates = [
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", r"C:\Program Files"), r"Google\Chrome\Application\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"), r"Google\Chrome\Application\chrome.exe"),
        shutil.which("msedge"),
        shutil.which("chrome"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def wait_for_server(port: int, max_retries: int = 50) -> bool:
    """Wait until backend server health check responds."""
    url = f"http://127.0.0.1:{port}/api/health"
    for _ in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    import uvicorn
    from app.core.config import settings
    from app.main import app

    port = find_free_port(settings.port)
    settings.port = port
    app_url = f"http://127.0.0.1:{port}"

    logger.info(f"Starting MultiLink v{settings.app_version} on {app_url}...")

    # Configure Uvicorn server instance
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for server readiness
    if not wait_for_server(port):
        logger.error("Timed out waiting for MultiLink backend to initialize.")
        server.should_exit = True
        return

    logger.info("Backend healthy. Launching desktop window...")

    browser_bin = get_browser_executable()
    app_data_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "MultiLink" / "browser_profile"
    app_data_dir.mkdir(parents=True, exist_ok=True)

    browser_proc = None
    if browser_bin:
        cmd = [
            browser_bin,
            f"--app={app_url}",
            f"--user-data-dir={app_data_dir}",
            "--window-size=1280,820",
            "--disable-features=TranslateUI",
            "--no-first-run",
            "--no-default-browser-check"
        ]
        try:
            browser_proc = subprocess.Popen(cmd)
        except Exception as e:
            logger.warning(f"Could not launch browser app mode: {e}. Opening default browser.")
            webbrowser.open(app_url)
    else:
        webbrowser.open(app_url)

    try:
        if browser_proc:
            # Wait for user to close the desktop window
            browser_proc.wait()
        else:
            # Keep running until killed
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Exit signal received.")
    finally:
        logger.info("Shutting down MultiLink server...")
        server.should_exit = True
        server_thread.join(timeout=3)
        logger.info("MultiLink closed successfully.")


if __name__ == "__main__":
    main()
