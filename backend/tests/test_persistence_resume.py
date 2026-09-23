import pytest
import tempfile
from pathlib import Path
from app.core.config import settings
from app.database.db import init_db
from app.database.repository import DownloadRepository
from app.models.schemas import Download, Chunk, DownloadStatus, ChunkStatus, OperatingMode

@pytest.mark.asyncio
async def test_persistence_and_resume():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Point db to temporary directory
        settings.db_path = Path(tmpdir) / "test.db"
        await init_db()

        # Create download
        dl = Download(
            id="dl_persist_1",
            url="https://example.com/data.zip",
            filename="data.zip",
            save_path=str(Path(tmpdir) / "data.zip"),
            total_size=1000,
            downloaded_size=250,
            status=DownloadStatus.DOWNLOADING,
            created_at="2026-09-22T00:00:00",
            updated_at="2026-09-22T00:00:00",
            mode=OperatingMode.MULTI_CONNECTION,
            chunks_total=2,
            chunks_completed=0
        )
        await DownloadRepository.create_download(dl)

        chunks = [
            Chunk(id="c1", download_id="dl_persist_1", chunk_index=0, start_byte=0, end_byte=499, downloaded_bytes=250, status=ChunkStatus.DOWNLOADING),
            Chunk(id="c2", download_id="dl_persist_1", chunk_index=1, start_byte=500, end_byte=999, downloaded_bytes=0, status=ChunkStatus.PENDING)
        ]
        await DownloadRepository.save_chunks(chunks)

        # Simulate application pause
        dl.status = DownloadStatus.PAUSED
        await DownloadRepository.update_download(dl)

        # Simulate application restart: load from DB
        fetched_dl = await DownloadRepository.get_download("dl_persist_1")
        assert fetched_dl is not None
        assert fetched_dl.status == DownloadStatus.PAUSED
        assert fetched_dl.downloaded_size == 250

        fetched_chunks = await DownloadRepository.get_chunks("dl_persist_1")
        assert len(fetched_chunks) == 2
        assert fetched_chunks[0].downloaded_bytes == 250
        assert fetched_chunks[1].start_byte == 500
