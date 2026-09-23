from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.database.db import init_db
from app.downloads.download_manager import download_manager
from app.api.routes import downloads, network, settings as settings_routes, ws
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("multilink.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Initializing {settings.app_name} v{settings.app_version}...")
    await init_db()
    await download_manager.start()
    yield
    logger.info("Shutting down MultiLink...")
    await download_manager.shutdown()

app = FastAPI(
    title="MultiLink Download Manager API",
    version=settings.app_version,
    lifespan=lifespan
)

# Strict CORS: Only allow local origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "active_downloads": len(download_manager._active_downloads),
        "downloads_dir": str(settings.downloads_dir)
    }

# Register routers
app.include_router(downloads.router)
app.include_router(network.router)
app.include_router(settings_routes.router)
app.include_router(ws.router)

import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

def get_frontend_dist_path() -> Path | None:
    # 1. PyInstaller bundled temp extraction directory
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundle_dist = Path(sys._MEIPASS) / "dist"
        if bundle_dist.exists():
            return bundle_dist
    
    # 2. Local workspace development layout
    workspace_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if workspace_dist.exists():
        return workspace_dist

    # 3. Adjacent dist directory
    adjacent_dist = Path(__file__).resolve().parent.parent / "dist"
    if adjacent_dist.exists():
        return adjacent_dist

    return None

frontend_dist = get_frontend_dist_path()
if frontend_dist and frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str = ""):
        target = frontend_dist / full_path
        if full_path and target.is_file():
            return FileResponse(str(target))
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"error": "MultiLink UI index.html not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)

