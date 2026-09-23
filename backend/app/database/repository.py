import json
from typing import List, Optional, Dict, Any
from app.database.db import get_db
from app.models.schemas import Download, Chunk, DownloadStatus, ChunkStatus, OperatingMode
import logging

logger = logging.getLogger("multilink.repo")

class DownloadRepository:
    @staticmethod
    async def create_download(dl: Download) -> None:
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO downloads (
                    id, url, filename, save_path, total_size, downloaded_size,
                    status, created_at, updated_at, completed_at, checksum, etag,
                    mime_type, range_supported, mode, error_message, chunks_total,
                    chunks_completed, selected_interfaces
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dl.id, dl.url, dl.filename, dl.save_path, dl.total_size, dl.downloaded_size,
                    dl.status.value, dl.created_at, dl.updated_at, dl.completed_at, dl.checksum, dl.etag,
                    dl.mime_type, 1 if dl.range_supported else 0, dl.mode.value, dl.error_message,
                    dl.chunks_total, dl.chunks_completed, json.dumps(dl.selected_interfaces)
                )
            )
            await db.commit()

    @staticmethod
    async def get_download(dl_id: str) -> Optional[Download]:
        async with get_db() as db:
            async with db.execute("SELECT * FROM downloads WHERE id = ?", (dl_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return Download(
                    id=row["id"],
                    url=row["url"],
                    filename=row["filename"],
                    save_path=row["save_path"],
                    total_size=row["total_size"],
                    downloaded_size=row["downloaded_size"],
                    status=DownloadStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    completed_at=row["completed_at"],
                    checksum=row["checksum"],
                    etag=row["etag"],
                    mime_type=row["mime_type"],
                    range_supported=bool(row["range_supported"]),
                    mode=OperatingMode(row["mode"]),
                    error_message=row["error_message"],
                    chunks_total=row["chunks_total"],
                    chunks_completed=row["chunks_completed"],
                    selected_interfaces=json.loads(row["selected_interfaces"] or "[]")
                )

    @staticmethod
    async def list_downloads() -> List[Download]:
        downloads = []
        async with get_db() as db:
            async with db.execute("SELECT * FROM downloads ORDER BY created_at DESC") as cursor:
                async for row in cursor:
                    downloads.append(Download(
                        id=row["id"],
                        url=row["url"],
                        filename=row["filename"],
                        save_path=row["save_path"],
                        total_size=row["total_size"],
                        downloaded_size=row["downloaded_size"],
                        status=DownloadStatus(row["status"]),
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        completed_at=row["completed_at"],
                        checksum=row["checksum"],
                        etag=row["etag"],
                        mime_type=row["mime_type"],
                        range_supported=bool(row["range_supported"]),
                        mode=OperatingMode(row["mode"]),
                        error_message=row["error_message"],
                        chunks_total=row["chunks_total"],
                        chunks_completed=row["chunks_completed"],
                        selected_interfaces=json.loads(row["selected_interfaces"] or "[]")
                    ))
        return downloads

    @staticmethod
    async def update_download(dl: Download) -> None:
        async with get_db() as db:
            await db.execute(
                """
                UPDATE downloads SET
                    url = ?,
                    filename = ?,
                    save_path = ?,
                    downloaded_size = ?,
                    status = ?,
                    updated_at = ?,
                    completed_at = ?,
                    checksum = ?,
                    error_message = ?,
                    chunks_completed = ?,
                    mode = ?
                WHERE id = ?
                """,
                (
                    dl.url, dl.filename, dl.save_path,
                    dl.downloaded_size, dl.status.value, dl.updated_at,
                    dl.completed_at, dl.checksum, dl.error_message,
                    dl.chunks_completed, dl.mode.value, dl.id
                )
            )
            await db.commit()

    @staticmethod
    async def delete_download(dl_id: str) -> None:
        async with get_db() as db:
            await db.execute("DELETE FROM chunks WHERE download_id = ?", (dl_id,))
            await db.execute("DELETE FROM downloads WHERE id = ?", (dl_id,))
            await db.commit()

    @staticmethod
    async def save_chunks(chunks: List[Chunk]) -> None:
        async with get_db() as db:
            data = [
                (
                    c.id, c.download_id, c.chunk_index, c.start_byte, c.end_byte,
                    c.downloaded_bytes, c.status.value, c.assigned_interface,
                    c.retry_count, c.speed_bps, c.start_time, c.completion_time, c.updated_at
                )
                for c in chunks
            ]
            await db.executemany(
                """
                INSERT OR REPLACE INTO chunks (
                    id, download_id, chunk_index, start_byte, end_byte,
                    downloaded_bytes, status, assigned_interface, retry_count,
                    speed_bps, start_time, completion_time, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data
            )
            await db.commit()

    @staticmethod
    async def get_chunks(dl_id: str) -> List[Chunk]:
        chunks = []
        async with get_db() as db:
            async with db.execute("SELECT * FROM chunks WHERE download_id = ? ORDER BY chunk_index ASC", (dl_id,)) as cursor:
                async for row in cursor:
                    chunks.append(Chunk(
                        id=row["id"],
                        download_id=row["download_id"],
                        chunk_index=row["chunk_index"],
                        start_byte=row["start_byte"],
                        end_byte=row["end_byte"],
                        downloaded_bytes=row["downloaded_bytes"],
                        status=ChunkStatus(row["status"]),
                        assigned_interface=row["assigned_interface"],
                        retry_count=row["retry_count"],
                        speed_bps=row["speed_bps"],
                        start_time=row["start_time"],
                        completion_time=row["completion_time"],
                        updated_at=row["updated_at"]
                    ))
        return chunks

    @staticmethod
    async def update_chunk(c: Chunk) -> None:
        async with get_db() as db:
            await db.execute(
                """
                UPDATE chunks SET
                    downloaded_bytes = ?,
                    status = ?,
                    assigned_interface = ?,
                    retry_count = ?,
                    speed_bps = ?,
                    start_time = ?,
                    completion_time = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    c.downloaded_bytes, c.status.value, c.assigned_interface,
                    c.retry_count, c.speed_bps, c.start_time, c.completion_time,
                    c.updated_at, c.id
                )
            )
            await db.commit()

    @staticmethod
    async def set_setting(key: str, value: str) -> None:
        async with get_db() as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            await db.commit()

    @staticmethod
    async def get_settings() -> Dict[str, str]:
        settings_dict = {}
        async with get_db() as db:
            async with db.execute("SELECT key, value FROM settings") as cursor:
                async for row in cursor:
                    settings_dict[row["key"]] = row["value"]
        return settings_dict
