import uuid
from typing import List
from app.models.schemas import Chunk, ChunkStatus
from app.core.config import settings

class ChunkManager:
    @staticmethod
    def calculate_optimal_chunk_size(total_size: int, user_chunk_size: int = None) -> int:
        if user_chunk_size and user_chunk_size > 0:
            return max(settings.min_chunk_size_bytes, min(user_chunk_size, settings.max_chunk_size_bytes))

        if total_size <= 0:
            return settings.default_chunk_size_bytes

        # Dynamic sizing based on file size:
        # < 50 MB: 4 MB chunks
        # 50 MB - 500 MB: 8 MB chunks
        # 500 MB - 5 GB: 16 MB chunks
        # 5 GB - 20 GB: 32 MB chunks
        # > 20 GB: 64 MB chunks
        if total_size < 50 * 1024 * 1024:
            return 4 * 1024 * 1024
        elif total_size < 500 * 1024 * 1024:
            return 8 * 1024 * 1024
        elif total_size < 5 * 1024 * 1024 * 1024:
            return 16 * 1024 * 1024
        elif total_size < 20 * 1024 * 1024 * 1024:
            return 32 * 1024 * 1024
        else:
            return 64 * 1024 * 1024

    @staticmethod
    def create_chunks(download_id: str, total_size: int, range_supported: bool, custom_chunk_size: int = None) -> List[Chunk]:
        chunks: List[Chunk] = []

        if not range_supported or total_size <= 0:
            # Single-stream non-ranged chunk
            chunks.append(Chunk(
                id=f"{download_id}_c0",
                download_id=download_id,
                chunk_index=0,
                start_byte=0,
                end_byte=total_size - 1 if total_size > 0 else 0,
                downloaded_bytes=0,
                status=ChunkStatus.PENDING,
                retry_count=0
            ))
            return chunks

        chunk_size = ChunkManager.calculate_optimal_chunk_size(total_size, custom_chunk_size)
        start = 0
        idx = 0
        while start < total_size:
            end = min(start + chunk_size - 1, total_size - 1)
            chunks.append(Chunk(
                id=f"{download_id}_c{idx}",
                download_id=download_id,
                chunk_index=idx,
                start_byte=start,
                end_byte=end,
                downloaded_bytes=0,
                status=ChunkStatus.PENDING,
                retry_count=0
            ))
            start = end + 1
            idx += 1

        return chunks
