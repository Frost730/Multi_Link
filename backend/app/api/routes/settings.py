from fastapi import APIRouter
from pathlib import Path
from app.models.schemas import SettingsModel
from app.core.config import settings
from app.database.repository import DownloadRepository
from app.networking.simulation import simulation_manager

router = APIRouter(prefix="/api/settings", tags=["Settings"])

@router.get("", response_model=SettingsModel)
async def get_settings_endpoint():
    db_settings = await DownloadRepository.get_settings()
    return SettingsModel(
        downloads_dir=db_settings.get("downloads_dir", str(settings.downloads_dir)),
        default_chunk_size_mb=int(db_settings.get("default_chunk_size_mb", settings.default_chunk_size_bytes // (1024 * 1024))),
        max_concurrent_connections=int(db_settings.get("max_concurrent_connections", settings.max_concurrent_connections_per_download)),
        max_retries=int(db_settings.get("max_retries", settings.max_retries_per_chunk)),
        allow_private_network_downloads=db_settings.get("allow_private_network_downloads", "0") == "1",
        simulation_mode_enabled=simulation_manager.enabled,
        verify_checksum=db_settings.get("verify_checksum", "1") == "1"
    )

@router.post("", response_model=SettingsModel)
async def update_settings_endpoint(req: SettingsModel):
    await DownloadRepository.set_setting("downloads_dir", req.downloads_dir)
    await DownloadRepository.set_setting("default_chunk_size_mb", str(req.default_chunk_size_mb))
    await DownloadRepository.set_setting("max_concurrent_connections", str(req.max_concurrent_connections))
    await DownloadRepository.set_setting("max_retries", str(req.max_retries))
    await DownloadRepository.set_setting("allow_private_network_downloads", "1" if req.allow_private_network_downloads else "0")
    await DownloadRepository.set_setting("verify_checksum", "1" if req.verify_checksum else "0")

    # Update in-memory settings
    settings.downloads_dir = Path(req.downloads_dir)
    settings.default_chunk_size_bytes = req.default_chunk_size_mb * 1024 * 1024
    settings.max_concurrent_connections_per_download = req.max_concurrent_connections
    settings.max_retries_per_chunk = req.max_retries
    settings.allow_private_network_downloads = req.allow_private_network_downloads
    simulation_manager.set_enabled(req.simulation_mode_enabled)

    return req
