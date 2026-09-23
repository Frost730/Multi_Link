import asyncio
import time
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from app.models.schemas import (
    Download, Chunk, DownloadStatus, ChunkStatus, OperatingMode, NetworkInterface
)
from app.database.repository import DownloadRepository
from app.downloads.assembler import FileAssembler
from app.downloads.integrity import IntegrityManager
from app.downloads.scheduler import DynamicScheduler
from app.networking.connection import NetworkConnection
from app.networking.interface_manager import interface_manager
from app.networking.simulation import simulation_manager
from app.networking.bandwidth_monitor import bandwidth_monitor
from app.core.events import event_bus
from app.core.config import settings
import logging

logger = logging.getLogger("multilink.manager")

class ActiveDownloadContext:
    def __init__(self, download: Download, chunks: List[Chunk], interfaces: List[NetworkInterface]):
        self.download = download
        self.chunks = {c.id: c for c in chunks}
        self.assembler = FileAssembler(Path(download.save_path), download.total_size)
        self.scheduler = DynamicScheduler(interfaces)
        self.stop_event = asyncio.Event()
        self.worker_tasks: Set[asyncio.Task] = set()
        self.coordinator_task: Optional[asyncio.Task] = None
        self.active_chunk_interface: Dict[str, str] = {}  # chunk_id -> interface_id
        self.connections: Dict[str, NetworkConnection] = {}
        self.start_time = time.time()
        self.last_downloaded_size = download.downloaded_size

        # Prepare connections for usable interfaces
        for iface in interfaces:
            is_selected = download.selected_interfaces and iface.id in download.selected_interfaces
            if (is_selected or iface.is_enabled or not download.selected_interfaces) and iface.usable:
                self.connections[iface.id] = NetworkConnection(
                    interface_id=iface.id,
                    local_ip=iface.ipv4,
                    is_simulated=iface.is_simulated
                )

class DownloadManager:
    def __init__(self):
        self._active_downloads: Dict[str, ActiveDownloadContext] = {}
        self._ticker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Start global telemetry ticker and resume queued/interrupted downloads if needed."""
        if self._ticker_task is None or self._ticker_task.done():
            self._ticker_task = asyncio.create_task(self._telemetry_ticker())
        logger.info("MultiLink Download Manager started.")

    async def shutdown(self):
        """Clean shutdown of all active download tasks."""
        if self._ticker_task:
            self._ticker_task.cancel()
        async with self._lock:
            for dl_id in list(self._active_downloads.keys()):
                await self.pause_download(dl_id)

    async def enqueue_download(self, download: Download, chunks: List[Chunk]) -> Download:
        await DownloadRepository.create_download(download)
        await DownloadRepository.save_chunks(chunks)

        # Broadcast created event
        await event_bus.emit("download_created", download.model_dump())

        # Start downloading
        asyncio.create_task(self.start_download(download.id))
        return download

    async def start_download(self, download_id: str):
        async with self._lock:
            if download_id in self._active_downloads:
                return

            dl = await DownloadRepository.get_download(download_id)
            if not dl:
                return

            chunks = await DownloadRepository.get_chunks(download_id)

            # Reset any failed or downloading chunks to PENDING so they are downloaded
            chunks_to_save = False
            for c in chunks:
                if c.status in (ChunkStatus.FAILED, ChunkStatus.DOWNLOADING):
                    c.status = ChunkStatus.PENDING
                    c.retry_count = 0
                    chunks_to_save = True
            if chunks_to_save:
                await DownloadRepository.save_chunks(chunks)

            # Get interfaces
            if simulation_manager.enabled or dl.mode == OperatingMode.SIMULATION_MODE:
                all_interfaces = simulation_manager.get_interfaces()
            else:
                all_interfaces = interface_manager.get_interfaces()

            # Filter interfaces by user selection if provided
            if dl.selected_interfaces:
                interfaces = [i for i in all_interfaces if i.id in dl.selected_interfaces and i.usable]
            else:
                interfaces = [i for i in all_interfaces if i.usable and i.is_enabled]

            # Fallback if no specific interface matched or enabled
            if not interfaces:
                interfaces = [i for i in all_interfaces if i.usable and i.status == "connected"]
            if not interfaces:
                interfaces = [i for i in all_interfaces if i.usable]
            if not interfaces:
                interfaces = all_interfaces

            ctx = ActiveDownloadContext(dl, chunks, interfaces)
            try:
                ctx.assembler.initialize()
            except Exception as e:
                dl.status = DownloadStatus.FAILED
                dl.error_message = f"Failed to initialize file: {e}"
                await DownloadRepository.update_download(dl)
                await event_bus.emit("download_failed", dl.model_dump())
                return

            self._active_downloads[download_id] = ctx
            dl.status = DownloadStatus.DOWNLOADING
            dl.updated_at = datetime.datetime.now().isoformat()
            await DownloadRepository.update_download(dl)
            await event_bus.emit("download_started", dl.model_dump())

            # Spawn coordinator task
            ctx.coordinator_task = asyncio.create_task(self._run_download_coordinator(ctx))

    async def pause_download(self, download_id: str) -> bool:
        async with self._lock:
            ctx = self._active_downloads.get(download_id)
            if not ctx:
                dl = await DownloadRepository.get_download(download_id)
                if dl and dl.status == DownloadStatus.DOWNLOADING:
                    dl.status = DownloadStatus.PAUSED
                    await DownloadRepository.update_download(dl)
                    await event_bus.emit("download_paused", dl.model_dump())
                return True

            ctx.stop_event.set()
            for task in list(ctx.worker_tasks):
                task.cancel()

            for conn in ctx.connections.values():
                await conn.close()
            ctx.assembler.close()

            # Update chunk statuses
            for chunk in ctx.chunks.values():
                if chunk.status == ChunkStatus.DOWNLOADING:
                    chunk.status = ChunkStatus.PENDING
            await DownloadRepository.save_chunks(list(ctx.chunks.values()))

            ctx.download.status = DownloadStatus.PAUSED
            ctx.download.updated_at = datetime.datetime.now().isoformat()
            await DownloadRepository.update_download(ctx.download)
            del self._active_downloads[download_id]

            await event_bus.emit("download_paused", ctx.download.model_dump())
            return True

    async def resume_download(self, download_id: str) -> bool:
        dl = await DownloadRepository.get_download(download_id)
        if not dl:
            return False
        if dl.status in (DownloadStatus.PAUSED, DownloadStatus.FAILED, DownloadStatus.QUEUED):
            # 1. Cleanly evict any stale in-memory active download context
            async with self._lock:
                if download_id in self._active_downloads:
                    ctx = self._active_downloads.pop(download_id)
                    ctx.stop_event.set()
                    for task in list(ctx.worker_tasks):
                        task.cancel()
                    for conn in ctx.connections.values():
                        await conn.close()
                    ctx.assembler.close()

            # 2. Rescue all failed and downloading chunks so they are retried
            chunks = await DownloadRepository.get_chunks(download_id)
            for c in chunks:
                if c.status in (ChunkStatus.FAILED, ChunkStatus.DOWNLOADING):
                    c.status = ChunkStatus.PENDING
                    c.retry_count = 0
            await DownloadRepository.save_chunks(chunks)

            dl.status = DownloadStatus.QUEUED
            dl.error_message = None
            await DownloadRepository.update_download(dl)

            await self.start_download(download_id)
            return True
        return False

    async def update_download_url(self, download_id: str, new_url: str) -> bool:
        """Updates download URL, rescues all failed chunks, cleans up stale context, and restarts download."""
        dl = await DownloadRepository.get_download(download_id)
        if not dl:
            return False

        # 1. Update in DB
        dl.url = new_url
        dl.error_message = None
        dl.status = DownloadStatus.QUEUED
        await DownloadRepository.update_download(dl)

        # 2. Rescue all failed chunks in DB
        chunks = await DownloadRepository.get_chunks(download_id)
        for c in chunks:
            if c.status in (ChunkStatus.FAILED, ChunkStatus.DOWNLOADING):
                c.status = ChunkStatus.PENDING
                c.retry_count = 0
        await DownloadRepository.save_chunks(chunks)

        # 3. Cleanly evict any stale in-memory active download context
        logger.info(f"Updating download {download_id} URL to {new_url[:80]}...")
        async with self._lock:
            if download_id in self._active_downloads:
                ctx = self._active_downloads.pop(download_id)
                ctx.stop_event.set()
                if ctx.coordinator_task and not ctx.coordinator_task.done():
                    ctx.coordinator_task.cancel()
                for task in list(ctx.worker_tasks):
                    task.cancel()
                for conn in ctx.connections.values():
                    await conn.close()
                ctx.assembler.close()

        # Brief yield to let cancelled tasks exit cleanly
        await asyncio.sleep(0.05)

        # 4. Broadcast event and start download immediately with the new URL
        await event_bus.emit("download_updated", dl.model_dump())
        await self.start_download(download_id)
        return True

    async def retry_failed_chunks(self, download_id: str) -> bool:
        """Rescues failed chunks for an active or stalled download and wakes up workers."""
        async with self._lock:
            ctx = self._active_downloads.get(download_id)
            if ctx:
                ctx.scheduler.chunk_failed_interfaces.clear()
                ctx.scheduler.failure_counts.clear()
                for chunk in ctx.chunks.values():
                    if chunk.status == ChunkStatus.FAILED:
                        chunk.status = ChunkStatus.PENDING
                        chunk.retry_count = 0
                await DownloadRepository.save_chunks(list(ctx.chunks.values()))
                ctx.download.error_message = None
                await DownloadRepository.update_download(ctx.download)
                return True

        # If not active in memory, resume cleanly
        return await self.resume_download(download_id)

    async def cancel_download(self, download_id: str) -> bool:
        await self.pause_download(download_id)
        dl = await DownloadRepository.get_download(download_id)
        if dl:
            dl.status = DownloadStatus.CANCELLED
            dl.updated_at = datetime.datetime.now().isoformat()
            await DownloadRepository.update_download(dl)
            part_file = Path(dl.save_path + ".multilink.part")
            if part_file.exists():
                try:
                    part_file.unlink()
                except Exception:
                    pass
            await event_bus.emit("download_cancelled", dl.model_dump())
        return True

    async def delete_download(self, download_id: str, delete_file: bool = False) -> bool:
        await self.cancel_download(download_id)
        dl = await DownloadRepository.get_download(download_id)
        if dl and delete_file:
            final_file = Path(dl.save_path)
            if final_file.exists():
                try:
                    final_file.unlink()
                except Exception:
                    pass
        await DownloadRepository.delete_download(download_id)
        await event_bus.emit("download_deleted", {"id": download_id})
        return True

    async def _run_download_coordinator(self, ctx: ActiveDownloadContext):
        """Coordinates chunk scheduling, worker lifecycle, and work stealing."""
        dl_id = ctx.download.id
        max_concurrency = min(
            settings.max_concurrent_connections_per_download,
            len(ctx.chunks)
        )

        try:
            while not ctx.stop_event.is_set():
                # Check for completion
                all_done = all(c.status == ChunkStatus.COMPLETED for c in ctx.chunks.values())
                if all_done:
                    await self._finalize_completed_download(ctx)
                    break

                # Clean completed worker tasks
                ctx.worker_tasks = {t for t in ctx.worker_tasks if not t.done()}

                # Work Stealing & Assignment: Fill idle worker slots
                while len(ctx.worker_tasks) < max_concurrency and not ctx.stop_event.is_set():
                    # 1. Find next pending chunk
                    pending_chunks = [
                        c for c in ctx.chunks.values()
                        if c.status == ChunkStatus.PENDING
                    ]

                    # 2. Work Stealing: If no pending chunks, rescue any failed chunks if healthy interfaces exist
                    if not pending_chunks:
                        failed_chunks = [
                            c for c in ctx.chunks.values()
                            if c.status == ChunkStatus.FAILED
                        ]
                        if failed_chunks and ctx.scheduler.has_healthy_interface():
                            rescued = failed_chunks[0]
                            rescued.status = ChunkStatus.PENDING
                            rescued.retry_count = 0
                            pending_chunks = [rescued]
                            logger.info(f"Work stealing: Rescued failed chunk {rescued.id} for healthy connection reassignment")

                    if not pending_chunks:
                        # If no pending chunks, no active workers, but failed chunks remain and no healthy interfaces
                        if len(ctx.worker_tasks) == 0 and any(c.status == ChunkStatus.FAILED for c in ctx.chunks.values()):
                            failed_count = sum(1 for c in ctx.chunks.values() if c.status == ChunkStatus.FAILED)
                            ctx.download.status = DownloadStatus.FAILED
                            ctx.download.error_message = f"{failed_count} chunks could not complete. Check network and click Resume to retry."
                            await DownloadRepository.update_download(ctx.download)
                            await event_bus.emit("download_failed", ctx.download.model_dump())
                            return
                        break

                    chunk = pending_chunks[0]
                    # Select best interface dynamically, avoiding interface that previously failed this chunk
                    best_if_id = ctx.scheduler.select_best_interface(
                        ctx.active_chunk_interface,
                        candidate_interface_ids=ctx.download.selected_interfaces or list(ctx.connections.keys()),
                        chunk_id=chunk.id
                    )

                    if not best_if_id or best_if_id not in ctx.connections:
                        if ctx.connections:
                            best_if_id = next(iter(ctx.connections.keys()))
                        else:
                            break

                    chunk.status = ChunkStatus.DOWNLOADING
                    chunk.assigned_interface = best_if_id
                    chunk.start_time = time.time()
                    ctx.active_chunk_interface[chunk.id] = best_if_id

                    task = asyncio.create_task(self._chunk_worker(ctx, chunk, best_if_id))
                    ctx.worker_tasks.add(task)

                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"Coordinator cancelled for download {dl_id}")
        except Exception as e:
            logger.exception(f"Error in coordinator for {dl_id}: {e}")
            ctx.download.status = DownloadStatus.FAILED
            ctx.download.error_message = f"Download error: {e}"
            await DownloadRepository.update_download(ctx.download)
            await event_bus.emit("download_failed", ctx.download.model_dump())
        finally:
            if ctx.download.status in (DownloadStatus.FAILED, DownloadStatus.PAUSED, DownloadStatus.CANCELLED):
                ctx.assembler.close()
                for conn in ctx.connections.values():
                    await conn.close()
                async with self._lock:
                    if self._active_downloads.get(dl_id) is ctx:
                        self._active_downloads.pop(dl_id, None)

    async def _chunk_worker(self, ctx: ActiveDownloadContext, chunk: Chunk, interface_id: str):
        conn = ctx.connections.get(interface_id)
        if not conn:
            chunk.status = ChunkStatus.PENDING
            ctx.active_chunk_interface.pop(chunk.id, None)
            return

        start_offset = chunk.start_byte + chunk.downloaded_bytes
        end_offset = chunk.end_byte

        if start_offset > end_offset:
            chunk.status = ChunkStatus.COMPLETED
            ctx.active_chunk_interface.pop(chunk.id, None)
            return

        chunk_start_time = time.time()

        async def on_write(offset: int, data: bytes):
            await ctx.assembler.write(offset, data)
            chunk.downloaded_bytes += len(data)
            ctx.download.downloaded_size += len(data)

        try:
            await conn.stream_range(
                url=ctx.download.url,
                start_byte=start_offset,
                end_byte=end_offset,
                write_callback=on_write,
                stop_event=ctx.stop_event
            )

            if ctx.stop_event.is_set():
                chunk.status = ChunkStatus.PENDING
                return

            chunk.status = ChunkStatus.COMPLETED
            chunk.completion_time = time.time()
            elapsed = chunk.completion_time - chunk_start_time
            if elapsed > 0:
                chunk.speed_bps = (chunk.downloaded_bytes * 8.0) / elapsed

            ctx.download.chunks_completed += 1
            ctx.scheduler.record_interface_success(interface_id)
            await DownloadRepository.update_chunk(chunk)
            await event_bus.emit("chunk_completed", chunk.model_dump())

        except Exception as e:
            err_str = str(e)
            is_permanent_http = any(code in err_str for code in ["401", "403", "404", "410"])
            chunk.retry_count += 1
            ctx.scheduler.record_chunk_failure(chunk.id, interface_id)
            logger.warning(f"Chunk {chunk.id} on {interface_id} failed ({err_str}). Retry {chunk.retry_count}/{settings.max_retries_per_chunk}")

            # If HTTP 401/403/404/410, allow other available interfaces to try first
            # (e.g. CDN token IP-binding causes 403 on Ethernet if token was issued for Wi-Fi IP)
            interfaces_exhausted = chunk.retry_count >= max(2, len(ctx.connections))
            should_fail_permanently = (is_permanent_http and interfaces_exhausted) or (chunk.retry_count >= settings.max_retries_per_chunk)

            if should_fail_permanently:
                chunk.status = ChunkStatus.FAILED
                if is_permanent_http:
                    ctx.download.error_message = f"Download link has expired or access denied ({err_str}). Please update the URL to resume."
                else:
                    ctx.download.error_message = f"Chunk {chunk.id} failed after {chunk.retry_count} attempts: {err_str}"
                await DownloadRepository.update_download(ctx.download)
                await event_bus.emit("download_failed", ctx.download.model_dump())
            else:
                # Return chunk to queue with backoff delay so another interface can take it!
                chunk.status = ChunkStatus.PENDING
                backoff_delay = min(0.5 * chunk.retry_count, 3.0)
                await asyncio.sleep(backoff_delay)

            await DownloadRepository.update_chunk(chunk)

        finally:
            ctx.active_chunk_interface.pop(chunk.id, None)

    async def _finalize_completed_download(self, ctx: ActiveDownloadContext):
        dl = ctx.download
        dl_id = dl.id
        ctx.assembler.close()
        for conn in ctx.connections.values():
            await conn.close()

        expected_checksum = dl.checksum if (dl.checksum and dl.status != DownloadStatus.COMPLETED) else None
        success, checksum, err = await IntegrityManager.verify_and_finalize(
            part_path=ctx.assembler.part_path,
            final_path=ctx.assembler.target_path,
            expected_size=dl.total_size,
            calculate_checksum=True,
            expected_checksum=expected_checksum
        )

        if success:
            dl.status = DownloadStatus.COMPLETED
            dl.checksum = checksum
            dl.error_message = None  # Clear any previous transient or stalled error message
            dl.completed_at = datetime.datetime.now().isoformat()
            dl.updated_at = dl.completed_at
            dl.downloaded_size = dl.total_size
            dl.chunks_completed = dl.chunks_total
            for c in ctx.chunks.values():
                c.status = ChunkStatus.COMPLETED
            await DownloadRepository.save_chunks(list(ctx.chunks.values()))
            await DownloadRepository.update_download(dl)
            await event_bus.emit("download_completed", dl.model_dump())
            logger.info(f"Download {dl.filename} completed successfully. SHA-256: {checksum}")
        else:
            dl.status = DownloadStatus.FAILED
            dl.error_message = f"Integrity check failed: {err}"
            await DownloadRepository.update_download(dl)
            await event_bus.emit("download_failed", dl.model_dump())
            logger.error(f"Integrity check failed for {dl.filename}: {err}")

        async with self._lock:
            if self._active_downloads.get(dl_id) is ctx:
                self._active_downloads.pop(dl_id, None)

    async def verify_download_integrity(self, download_id: str) -> Optional[dict]:
        """Perform on-demand file integrity, byte-size, and chunk completeness verification."""
        dl = await DownloadRepository.get_download(download_id)
        if not dl:
            return None

        target_file = Path(dl.save_path)
        part_file = Path(dl.save_path + ".multilink.part")
        file_to_check = target_file if target_file.exists() else (part_file if part_file.exists() else None)

        if not file_to_check:
            return {
                "verified": False,
                "status": "FILE_NOT_FOUND",
                "download_id": download_id,
                "filename": dl.filename,
                "file_path": str(target_file),
                "file_exists": False,
                "actual_size": 0,
                "expected_size": dl.total_size,
                "size_matches": False,
                "sha256": "",
                "chunks_total": dl.chunks_total,
                "chunks_completed": dl.chunks_completed,
                "failed_chunk_count": 0,
                "pending_chunk_count": 0,
                "message": f"Downloaded file does not exist on disk at {target_file}"
            }

        actual_size = file_to_check.stat().st_size
        expected_size = dl.total_size
        size_matches = (expected_size <= 0) or (actual_size == expected_size)

        chunks = await DownloadRepository.get_chunks(download_id)
        total_chunks = len(chunks)
        failed_chunks = [c.chunk_index for c in chunks if c.status == ChunkStatus.FAILED]
        pending_chunks = [c.chunk_index for c in chunks if c.status == ChunkStatus.PENDING]
        completed_chunks = [c for c in chunks if c.status == ChunkStatus.COMPLETED]
        chunks_ok = (len(failed_chunks) == 0 and len(pending_chunks) == 0)

        # Calculate actual SHA-256 hash
        try:
            sha256 = await IntegrityManager.compute_sha256(file_to_check)
        except Exception as e:
            sha256 = f"Error: {e}"

        hash_matches = True
        if dl.checksum and sha256 and not sha256.startswith("Error"):
            if dl.checksum.lower() != sha256.lower():
                hash_matches = False
        elif sha256 and not sha256.startswith("Error"):
            dl.checksum = sha256

        # If file is complete and size matches, clean any lingering error message
        if size_matches and (dl.status == DownloadStatus.COMPLETED or actual_size == expected_size):
            dl.status = DownloadStatus.COMPLETED
            dl.error_message = None
            dl.downloaded_size = actual_size
            dl.chunks_completed = total_chunks
            for c in chunks:
                c.status = ChunkStatus.COMPLETED
            await DownloadRepository.save_chunks(chunks)
            await DownloadRepository.update_download(dl)

        verified = size_matches and hash_matches and (chunks_ok or dl.status == DownloadStatus.COMPLETED)

        if verified:
            message = f"Integrity 100% verified. File size ({actual_size:,} bytes) matches expected size with 0 missing chunks. SHA-256 confirmed."
        elif not size_matches:
            message = f"File size mismatch: Found {actual_size:,} bytes on disk, but expected {expected_size:,} bytes."
        elif not hash_matches:
            message = f"Checksum mismatch: Expected {dl.checksum}, but computed {sha256}."
        else:
            message = f"{len(failed_chunks)} chunks failed and {len(pending_chunks)} chunks pending."

        return {
            "verified": verified,
            "status": "VERIFIED" if verified else "CORRUPTED",
            "download_id": download_id,
            "filename": dl.filename,
            "file_path": str(file_to_check),
            "file_exists": True,
            "actual_size": actual_size,
            "expected_size": expected_size,
            "size_matches": size_matches,
            "sha256": sha256,
            "chunks_total": total_chunks,
            "chunks_completed": total_chunks if verified else len(completed_chunks),
            "failed_chunk_count": 0 if verified else len(failed_chunks),
            "pending_chunk_count": 0 if verified else len(pending_chunks),
            "message": message
        }

    async def _telemetry_ticker(self):
        """Tick every 1 second: update speeds, ETA, write progress to DB every 5s, emit WebSocket telemetry."""
        db_sync_counter = 0
        while True:
            try:
                await asyncio.sleep(1.0)
                db_sync_counter += 1
                speed_point = bandwidth_monitor.tick_history()
                combined_speed = speed_point.combined_bps

                async with self._lock:
                    active_items = list(self._active_downloads.values())

                for ctx in active_items:
                    dl = ctx.download
                    dl.current_speed_bps = combined_speed

                    remaining_bytes = max(0, dl.total_size - dl.downloaded_size)
                    if combined_speed > 1000 and remaining_bytes > 0:
                        dl.eta_seconds = (remaining_bytes * 8.0) / combined_speed
                    else:
                        dl.eta_seconds = None

                    elapsed = time.time() - ctx.start_time
                    if elapsed > 0:
                        dl.average_speed_bps = (dl.downloaded_size * 8.0) / elapsed

                    # Debounce SQLite disk writes to every 5 seconds to reduce lock contention
                    if db_sync_counter % 5 == 0:
                        await DownloadRepository.update_download(dl)

                await event_bus.emit("speed_update", {
                    "timestamp": speed_point.timestamp,
                    "combined_bps": speed_point.combined_bps,
                    "interfaces": speed_point.interfaces,
                    "active_downloads_count": len(active_items)
                })

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Telemetry ticker error: {e}")

download_manager = DownloadManager()
