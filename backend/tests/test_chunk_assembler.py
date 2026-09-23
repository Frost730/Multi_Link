import pytest
import asyncio
import tempfile
import hashlib
from pathlib import Path
from app.downloads.chunk_manager import ChunkManager
from app.downloads.assembler import FileAssembler
from app.downloads.integrity import IntegrityManager

def test_chunk_manager_division():
    total_size = 100 * 1024 * 1024  # 100 MB
    chunks = ChunkManager.create_chunks("dl_1", total_size, range_supported=True, custom_chunk_size=16 * 1024 * 1024)
    assert len(chunks) == 7
    assert chunks[0].start_byte == 0
    assert chunks[0].end_byte == 16 * 1024 * 1024 - 1
    assert chunks[-1].end_byte == total_size - 1

def test_chunk_manager_non_ranged():
    chunks = ChunkManager.create_chunks("dl_2", 5000, range_supported=False)
    assert len(chunks) == 1
    assert chunks[0].start_byte == 0
    assert chunks[0].end_byte == 4999

@pytest.mark.asyncio
async def test_assembler_sparse_and_integrity():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "output.bin"
        data_part1 = b"Hello, "
        data_part2 = b"MultiLink!"
        total_len = len(data_part1) + len(data_part2)

        assembler = FileAssembler(target, total_len)
        assembler.initialize()

        # Write out-of-order
        await assembler.write(len(data_part1), data_part2)
        await assembler.write(0, data_part1)
        assembler.close()

        success, sha, err = await IntegrityManager.verify_and_finalize(
            part_path=assembler.part_path,
            final_path=assembler.target_path,
            expected_size=total_len,
            calculate_checksum=True
        )

        assert success is True
        assert target.exists()
        assert target.read_bytes() == b"Hello, MultiLink!"
        expected_sha = hashlib.sha256(b"Hello, MultiLink!").hexdigest()
        assert sha == expected_sha
