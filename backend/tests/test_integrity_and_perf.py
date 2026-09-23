import pytest
import asyncio
import tempfile
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import aiohttp
from aiohttp import web

from app.downloads.assembler import FileAssembler, _enable_sparse_file_windows
from app.downloads.integrity import IntegrityManager
from app.networking.connection import NetworkConnection

@pytest.mark.asyncio
async def test_assembler_pipeline_and_bounds():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "test_perf.bin"
        total_size = 1024 * 1024  # 1 MB

        assembler = FileAssembler(target, total_size, queue_maxsize=32)
        assembler.initialize()

        # Concurrent chunk writes
        data_a = b"A" * 65536
        data_b = b"B" * 65536
        data_c = b"C" * 65536

        # Write concurrently
        await asyncio.gather(
            assembler.write(131072, data_c),
            assembler.write(0, data_a),
            assembler.write(65536, data_b),
        )

        assembler.flush()
        assembler.close()

        assert assembler.part_path.exists()
        assert assembler.part_path.stat().st_size == total_size

        content = assembler.part_path.read_bytes()
        assert content[0:65536] == data_a
        assert content[65536:131072] == data_b
        assert content[131072:196608] == data_c

        # Verify out-of-bounds error
        assembler2 = FileAssembler(target, 100)
        assembler2.initialize()
        with pytest.raises(ValueError, match="out of bounds"):
            await assembler2.write(90, b"X" * 20)
        assembler2.close()

@pytest.mark.asyncio
async def test_integrity_multi_algorithms():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "data.bin"
        payload = b"High-speed multi-network download manager verification payload 1234567890"
        test_file.write_bytes(payload)

        expected_md5 = hashlib.md5(payload).hexdigest()
        expected_sha1 = hashlib.sha1(payload).hexdigest()
        expected_sha256 = hashlib.sha256(payload).hexdigest()

        # Check algorithm detection
        assert IntegrityManager.detect_hash_algorithm(expected_md5) == "md5"
        assert IntegrityManager.detect_hash_algorithm(expected_sha1) == "sha1"
        assert IntegrityManager.detect_hash_algorithm(expected_sha256) == "sha256"

        # Compute hashes
        md5_calc = await IntegrityManager.compute_hash(test_file, "md5")
        sha1_calc = await IntegrityManager.compute_hash(test_file, "sha1")
        sha256_calc = await IntegrityManager.compute_sha256(test_file)

        assert md5_calc == expected_md5
        assert sha1_calc == expected_sha1
        assert sha256_calc == expected_sha256

        # Test verify_and_finalize with matching expected checksum
        final_target = Path(tmpdir) / "final.bin"
        success, hash_out, err = await IntegrityManager.verify_and_finalize(
            part_path=test_file,
            final_path=final_target,
            expected_size=len(payload),
            expected_checksum=expected_sha256
        )
        assert success is True
        assert err is None
        assert hash_out == expected_sha256
        assert final_target.exists()

@pytest.mark.asyncio
async def test_integrity_checksum_mismatch():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "corrupt.part"
        final_target = Path(tmpdir) / "corrupt.bin"
        payload = b"Corrupted data stream"
        test_file.write_bytes(payload)

        wrong_sha256 = "0" * 64
        success, hash_out, err = await IntegrityManager.verify_and_finalize(
            part_path=test_file,
            final_path=final_target,
            expected_size=len(payload),
            expected_checksum=wrong_sha256
        )
        assert success is False
        assert "Checksum mismatch" in err
        assert not final_target.exists()
        assert test_file.exists()  # Part file preserved on failure for diagnosis

@pytest.mark.asyncio
async def test_connection_range_guard():
    # Setup mock server that wrongly returns 200 for a range request
    async def bad_range_handler(request):
        # Server ignores Range header and returns 200 with full content
        return web.Response(text="Full content from byte 0", status=200)

    app = web.Application()
    app.router.add_get("/bad-range", bad_range_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    server_port = site._server.sockets[0].getsockname()[1]
    bad_url = f"http://127.0.0.1:{server_port}/bad-range"

    try:
        conn = NetworkConnection(interface_id="loopback_test", local_ip=None)
        stop_ev = asyncio.Event()
        written = bytearray()

        async def on_write(offset: int, data: bytes):
            written.extend(data)

        # When start_byte > 0, HTTP 200 MUST be rejected to protect file integrity
        with pytest.raises(RuntimeError, match="Server returned full content"):
            await conn.stream_range(
                url=bad_url,
                start_byte=100,
                end_byte=200,
                write_callback=on_write,
                stop_event=stop_ev
            )
        await conn.close()
    finally:
        await runner.cleanup()
