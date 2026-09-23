from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import uuid
import datetime
from pathlib import Path

from app.models.schemas import (
    AnalyzeRequest, AnalyzeResponse, DownloadCreate, Download, Chunk, DownloadStatus, OperatingMode
)
from app.downloads.metadata import probe_url
from app.downloads.chunk_manager import ChunkManager
from app.downloads.download_manager import download_manager
from app.database.repository import DownloadRepository
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import sanitize_filename, validate_url

router = APIRouter(prefix="/api/downloads", tags=["Downloads"])

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_url_endpoint(req: AnalyzeRequest):
    try:
        resp = await probe_url(req.url, allow_private=settings.allow_private_network_downloads)
        return resp
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze URL: {e}")

@router.post("", response_model=Download)
async def create_download_endpoint(req: DownloadCreate):
    try:
        meta = await probe_url(req.url, allow_private=settings.allow_private_network_downloads)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot initialize download: {e}")

    dl_id = str(uuid.uuid4())[:8]
    chosen_filename = sanitize_filename(req.filename or meta.filename)
    save_dir = Path(req.save_path) if req.save_path else settings.downloads_dir
    save_dir.mkdir(parents=True, exist_ok=True)
    target_filepath = save_dir / chosen_filename

    # If file already exists, adjust filename with index
    counter = 1
    while target_filepath.exists():
        stem = Path(chosen_filename).stem
        ext = Path(chosen_filename).suffix
        target_filepath = save_dir / f"{stem}_{counter}{ext}"
        counter += 1

    custom_chunk_bytes = (req.custom_chunk_size_mb * 1024 * 1024) if req.custom_chunk_size_mb else None
    chunks = ChunkManager.create_chunks(
        download_id=dl_id,
        total_size=meta.total_size,
        range_supported=meta.range_supported,
        custom_chunk_size=custom_chunk_bytes
    )

    now_iso = datetime.datetime.now().isoformat()
    download = Download(
        id=dl_id,
        url=req.url,
        filename=target_filepath.name,
        save_path=str(target_filepath),
        total_size=meta.total_size,
        downloaded_size=0,
        status=DownloadStatus.QUEUED,
        created_at=now_iso,
        updated_at=now_iso,
        range_supported=meta.range_supported,
        mode=meta.suggested_mode,
        chunks_total=len(chunks),
        chunks_completed=0,
        mime_type=meta.mime_type,
        selected_interfaces=req.selected_interfaces or []
    )

    await download_manager.enqueue_download(download, chunks)
    return download

@router.get("", response_model=List[Download])
async def list_downloads_endpoint():
    downloads = await DownloadRepository.list_downloads()
    # Enrich with live context info if active
    for dl in downloads:
        if dl.id in download_manager._active_downloads:
            ctx = download_manager._active_downloads[dl.id]
            dl.status = ctx.download.status
            dl.downloaded_size = ctx.download.downloaded_size
            dl.current_speed_bps = ctx.download.current_speed_bps
            dl.average_speed_bps = ctx.download.average_speed_bps
            dl.eta_seconds = ctx.download.eta_seconds
            dl.chunks_completed = ctx.download.chunks_completed
            if ctx.download.checksum:
                dl.checksum = ctx.download.checksum
    return downloads

@router.get("/{download_id}", response_model=Download)
async def get_download_endpoint(download_id: str):
    dl = await DownloadRepository.get_download(download_id)
    if not dl:
        raise HTTPException(status_code=404, detail="Download not found")
    if dl.id in download_manager._active_downloads:
        ctx = download_manager._active_downloads[dl.id]
        dl.status = ctx.download.status
        dl.downloaded_size = ctx.download.downloaded_size
        dl.current_speed_bps = ctx.download.current_speed_bps
        dl.average_speed_bps = ctx.download.average_speed_bps
        dl.eta_seconds = ctx.download.eta_seconds
        dl.chunks_completed = ctx.download.chunks_completed
        if ctx.download.checksum:
            dl.checksum = ctx.download.checksum
    return dl

@router.get("/{download_id}/chunks", response_model=List[Chunk])
async def get_download_chunks_endpoint(download_id: str):
    # If active in memory, return live chunk states
    if download_id in download_manager._active_downloads:
        ctx = download_manager._active_downloads[download_id]
        return list(ctx.chunks.values())
    chunks = await DownloadRepository.get_chunks(download_id)
    return chunks

@router.post("/{download_id}/pause")
async def pause_download_endpoint(download_id: str):
    success = await download_manager.pause_download(download_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")
    return {"status": "paused", "id": download_id}

@router.post("/{download_id}/resume")
async def resume_download_endpoint(download_id: str):
    success = await download_manager.resume_download(download_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found or cannot be resumed")
    return {"status": "resumed", "id": download_id}

@router.post("/{download_id}/cancel")
async def cancel_download_endpoint(download_id: str):
    success = await download_manager.cancel_download(download_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")
    return {"status": "cancelled", "id": download_id}

@router.delete("/{download_id}")
async def delete_download_endpoint(download_id: str, delete_file: bool = Query(default=False)):
    success = await download_manager.delete_download(download_id, delete_file=delete_file)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")
    return {"status": "deleted", "id": download_id}

class UpdateUrlRequest(BaseModel):
    url: str

@router.post("/{download_id}/update-url")
async def update_download_url_endpoint(download_id: str, req: UpdateUrlRequest):
    is_valid, err = validate_url(req.url, allow_private=settings.allow_private_network_downloads)
    if not is_valid:
        raise HTTPException(status_code=400, detail=err)

    success = await download_manager.update_download_url(download_id, req.url)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")

    return {"status": "updated", "id": download_id, "url": req.url}

@router.post("/{download_id}/retry-failed")
async def retry_failed_endpoint(download_id: str):
    success = await download_manager.retry_failed_chunks(download_id)
    if not success:
        raise HTTPException(status_code=404, detail="Download not found")
    return {"status": "retrying", "id": download_id}
