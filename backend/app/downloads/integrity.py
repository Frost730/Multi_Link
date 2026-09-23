import hashlib
import os
import shutil
from pathlib import Path
from typing import Tuple, Optional
import asyncio
import logging

logger = logging.getLogger("multilink.integrity")

class IntegrityManager:
    @staticmethod
    def detect_hash_algorithm(hash_str: str) -> str:
        """Auto-detects hash algorithm from hex digest length."""
        clean = hash_str.strip().lower()
        if len(clean) == 32:
            return "md5"
        elif len(clean) == 40:
            return "sha1"
        elif len(clean) == 64:
            return "sha256"
        return "sha256"

    @staticmethod
    def _compute_hash_sync(file_path: Path, algorithm: str = "sha256") -> str:
        algo = algorithm.lower()
        if algo == "md5":
            hasher = hashlib.md5()
        elif algo == "sha1":
            hasher = hashlib.sha1()
        else:
            hasher = hashlib.sha256()

        with open(file_path, "rb") as f:
            # 8 MB high-throughput buffer for NVMe/SSD streaming
            while chunk := f.read(8 * 1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    async def compute_hash(file_path: Path, algorithm: str = "sha256") -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, IntegrityManager._compute_hash_sync, file_path, algorithm)

    @staticmethod
    async def compute_sha256(file_path: Path) -> str:
        return await IntegrityManager.compute_hash(file_path, "sha256")

    @staticmethod
    async def verify_and_finalize(
        part_path: Path,
        final_path: Path,
        expected_size: int,
        calculate_checksum: bool = True,
        expected_checksum: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Verifies expected size, computes hash (SHA-256 or matched expected algorithm),
        verifies against expected_checksum if provided, and atomically finalizes the file.
        Returns: (success, computed_checksum, error_message)
        """
        if not part_path.exists():
            return False, None, f"Part file does not exist: {part_path}"

        actual_size = part_path.stat().st_size
        if expected_size > 0 and actual_size != expected_size:
            return False, None, f"Size mismatch: expected {expected_size} bytes, found {actual_size} bytes."

        checksum = None
        if expected_checksum:
            algo = IntegrityManager.detect_hash_algorithm(expected_checksum)
            try:
                checksum = await IntegrityManager.compute_hash(part_path, algo)
            except Exception as e:
                return False, None, f"Failed to compute {algo} checksum: {e}"

            if checksum.lower() != expected_checksum.strip().lower():
                return False, checksum, (
                    f"Checksum mismatch: expected {expected_checksum.strip().lower()} "
                    f"({algo.upper()}), but calculated {checksum}."
                )
        elif calculate_checksum:
            try:
                checksum = await IntegrityManager.compute_sha256(part_path)
            except Exception as e:
                logger.warning(f"Failed to calculate SHA-256 checksum: {e}")

        try:
            # Atomic rename / replace
            if final_path.exists():
                final_path.unlink()
            part_path.rename(final_path)
            logger.info(f"Successfully finalized file: {final_path}")
            return True, checksum, None
        except Exception as e:
            try:
                # Fallback to copy and remove if cross-volume or temporarily locked
                shutil.move(str(part_path), str(final_path))
                return True, checksum, None
            except Exception as err2:
                return False, None, f"Failed to rename part file to final destination: {err2}"
