import pytest
import asyncio
import tempfile
import hashlib
from pathlib import Path
from aiohttp import web
from app.core.config import settings
from app.database.db import init_db
from app.downloads.metadata import probe_url
from app.downloads.chunk_manager import ChunkManager
from app.downloads.download_manager import download_manager
from app.models.schemas import Download, DownloadStatus, OperatingMode
from app.database.repository import DownloadRepository

TEST_PAYLOAD = b"MultiLink-HighSpeed-Network-Engine-Validation-Payload-Data" * 200000  # ~11.6 MB
PAYLOAD_SHA = hashlib.sha256(TEST_PAYLOAD).hexdigest()

async def mock_file_handler(request: web.Request):
    range_header = request.headers.get("Range")
    total_len = len(TEST_PAYLOAD)

    if range_header and range_header.startswith("bytes="):
        # Format: bytes=START-END
        byte_range = range_header[6:].split("-")
        start = int(byte_range[0])
        end = int(byte_range[1]) if byte_range[1] else total_len - 1
        end = min(end, total_len - 1)

        body = TEST_PAYLOAD[start:end + 1]
        headers = {
            "Content-Range": f"bytes {start}-{end}/{total_len}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(body)),
            "Content-Type": "application/octet-stream"
        }
        return web.Response(body=body, status=206, headers=headers)

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(total_len),
        "Content-Type": "application/octet-stream"
    }
    return web.Response(body=TEST_PAYLOAD, status=200, headers=headers)

@pytest.mark.asyncio
async def test_full_e2e_multi_chunk_download():
    # 1. Start mock range server
    app = web.Application()
    app.router.add_get("/testfile.dat", mock_file_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    
    server_port = site._server.sockets[0].getsockname()[1]
    test_url = f"http://127.0.0.1:{server_port}/testfile.dat"

    with tempfile.TemporaryDirectory() as tmpdir:
        settings.db_path = Path(tmpdir) / "multilink.db"
        settings.downloads_dir = Path(tmpdir) / "downloads"
        settings.downloads_dir.mkdir(parents=True, exist_ok=True)
        settings.allow_private_network_downloads = True  # Allow test server
        await init_db()
        await download_manager.start()

        # 2. Probe URL
        meta = await probe_url(test_url, allow_private=True)
        assert meta.range_supported is True
        assert meta.total_size == len(TEST_PAYLOAD)

        # 3. Create chunks (2 MB chunk size for multiple parallel ranges)
        dl_id = "test_e2e_1"
        chunks = ChunkManager.create_chunks(
            download_id=dl_id,
            total_size=meta.total_size,
            range_supported=True,
            custom_chunk_size=2 * 1024 * 1024
        )
        assert len(chunks) >= 5

        target_file = settings.downloads_dir / "testfile.dat"
        dl = Download(
            id=dl_id,
            url=test_url,
            filename="testfile.dat",
            save_path=str(target_file),
            total_size=meta.total_size,
            downloaded_size=0,
            status=DownloadStatus.QUEUED,
            created_at="2026-09-22T00:00:00",
            updated_at="2026-09-22T00:00:00",
            range_supported=True,
            mode=OperatingMode.MULTI_CONNECTION,
            chunks_total=len(chunks),
            chunks_completed=0
        )

        # 4. Enqueue download
        await download_manager.enqueue_download(dl, chunks)

        # 5. Wait for download completion (max 20s)
        completed = False
        for _ in range(200):
            await asyncio.sleep(0.1)
            record = await DownloadRepository.get_download(dl_id)
            if record and record.status == DownloadStatus.COMPLETED:
                completed = True
                break

        assert completed is True
        assert target_file.exists()
        assert target_file.stat().st_size == len(TEST_PAYLOAD)

        # 6. Verify byte-by-byte SHA-256
        downloaded_bytes = target_file.read_bytes()
        downloaded_sha = hashlib.sha256(downloaded_bytes).hexdigest()
        assert downloaded_sha == PAYLOAD_SHA

        await download_manager.shutdown()

    await runner.cleanup()
