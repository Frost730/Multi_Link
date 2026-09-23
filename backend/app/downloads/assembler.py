import os
import asyncio
from pathlib import Path
import queue
import threading
import logging

logger = logging.getLogger("multilink.assembler")

def _enable_sparse_file_windows(fd: int) -> bool:
    """Marks an NTFS file as sparse so seek-allocations are instantaneous."""
    if os.name != "nt":
        return False
    try:
        import msvcrt
        import ctypes
        from ctypes import wintypes

        FSCTL_SET_SPARSE = 0x000900C4
        handle = msvcrt.get_osfhandle(fd)
        bytes_returned = wintypes.DWORD()
        success = ctypes.windll.kernel32.DeviceIoControl(
            handle,
            FSCTL_SET_SPARSE,
            None, 0,
            None, 0,
            ctypes.byref(bytes_returned),
            None
        )
        return bool(success)
    except Exception as e:
        logger.debug(f"Could not enable sparse allocation on fd {fd}: {e}")
        return False

class FileAssembler:
    def __init__(self, target_path: Path, total_size: int, queue_maxsize: int = 256):
        self.target_path = Path(target_path)
        self.part_path = Path(str(target_path) + ".multilink.part")
        self.total_size = total_size
        self._file = None
        self._write_queue: queue.Queue = queue.Queue(maxsize=queue_maxsize)
        self._writer_thread: threading.Thread = None
        self._writer_error: Exception = None
        self._closed = False
        self._lock = threading.Lock()

    def initialize(self):
        with self._lock:
            self.part_path.parent.mkdir(parents=True, exist_ok=True)
            # Open in read-write binary mode (create if not exists)
            is_new = not self.part_path.exists()
            if is_new:
                self._file = open(self.part_path, "wb+")
                if self.total_size > 0:
                    # Attempt Windows NTFS sparse flag
                    _enable_sparse_file_windows(self._file.fileno())
                    # Seek to total_size - 1 and write a single byte
                    self._file.seek(self.total_size - 1)
                    self._file.write(b"\0")
                    self._file.flush()
            else:
                self._file = open(self.part_path, "r+b")

            self._closed = False
            self._writer_error = None
            self._writer_thread = threading.Thread(
                target=self._writer_loop,
                name=f"AssemblerWriter-{self.part_path.name}",
                daemon=True
            )
            self._writer_thread.start()

    def _writer_loop(self):
        """Single-threaded high-throughput background writer loop."""
        writes_since_flush = 0
        while True:
            try:
                item = self._write_queue.get()
                if item is None:
                    # Sentinel: end of queue
                    self._write_queue.task_done()
                    break

                offset, data = item
                if self._file and not self._file.closed:
                    self._file.seek(offset)
                    self._file.write(data)
                    writes_since_flush += 1

                    # Periodically flush every 32 writes to release OS disk cache pressure
                    if writes_since_flush >= 32:
                        self._file.flush()
                        writes_since_flush = 0

                self._write_queue.task_done()
            except Exception as e:
                logger.error(f"Writer loop error on {self.part_path}: {e}")
                self._writer_error = e
                try:
                    self._write_queue.task_done()
                except ValueError:
                    pass

    async def write(self, offset: int, data: bytes):
        """Asynchronously queues chunk data to the dedicated disk writer pipeline."""
        if self._writer_error:
            raise RuntimeError(f"FileAssembler writer failed: {self._writer_error}")
        if self._closed:
            raise RuntimeError("Cannot write to closed FileAssembler")

        # Boundary integrity guard
        if self.total_size > 0 and offset + len(data) > self.total_size:
            raise ValueError(
                f"Write offset out of bounds: offset={offset}, len={len(data)}, total_size={self.total_size}"
            )

        # Fast path: non-blocking queue push
        try:
            self._write_queue.put_nowait((offset, data))
        except queue.Full:
            # Backpressure: wait for queue space in executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._write_queue.put, (offset, data))

    def flush(self):
        """Waits for pending writes in queue to complete and flushes file buffer."""
        if self._closed:
            return
        # Wait for all currently enqueued tasks to be processed
        self._write_queue.join()
        with self._lock:
            if self._file and not self._file.closed:
                self._file.flush()

    def close(self):
        """Drains the write pipeline, fsyncs data to disk, and closes file handle."""
        with self._lock:
            if self._closed:
                return
            self._closed = True

        # Send sentinel to terminate writer thread and wait for completion
        if self._writer_thread and self._writer_thread.is_alive():
            self._write_queue.put(None)
            self._writer_thread.join(timeout=10.0)

        with self._lock:
            if self._file and not self._file.closed:
                try:
                    self._file.flush()
                    os.fsync(self._file.fileno())
                except OSError:
                    pass
                self._file.close()
                self._file = None
