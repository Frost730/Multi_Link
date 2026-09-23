import aiohttp
import asyncio
from urllib.parse import urlparse
from typing import Optional, Callable, Awaitable
from app.networking.bandwidth_monitor import bandwidth_monitor
from app.networking.simulation import simulation_manager
import logging

logger = logging.getLogger("multilink.connection")

class NetworkConnection:
    def __init__(self, interface_id: str, local_ip: Optional[str] = None, is_simulated: bool = False):
        self.interface_id = interface_id
        self.local_ip = local_ip
        self.is_simulated = is_simulated
        self.session: Optional[aiohttp.ClientSession] = None
        self.is_bound = False
        self.last_error: Optional[str] = None
        self.binding_disabled = False  # permanently disable binding for this interface if OS routing rejects it

    async def open(self, target_host: Optional[str] = None):
        if self.session and not self.session.closed:
            return

        timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_read=45)
        is_loopback_target = target_host in ("127.0.0.1", "localhost", "::1", "0.0.0.0")

        # Only attempt actual local IP binding if configured, not simulated, not loopback, and binding hasn't failed
        if self.local_ip and not self.is_simulated and not is_loopback_target and not self.binding_disabled:
            try:
                connector = aiohttp.TCPConnector(
                    local_addr=(self.local_ip, 0),
                    limit=20,
                    ssl=False
                )
                self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
                self.is_bound = True
                logger.info(f"Connection for interface {self.interface_id} bound to {self.local_ip}")
            except Exception as e:
                logger.warning(f"Binding to {self.local_ip} failed ({e}). Falling back to unbound connector.")
                self.is_bound = False
                self.binding_disabled = True
                self.last_error = f"Socket bind fallback: {e}"
                connector = aiohttp.TCPConnector(limit=20)
                self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        else:
            connector = aiohttp.TCPConnector(limit=20)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
            self.is_bound = False

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def stream_range(
        self,
        url: str,
        start_byte: int,
        end_byte: int,
        write_callback: Callable[[int, bytes], Awaitable[None]],
        stop_event: asyncio.Event,
        progress_callback: Optional[Callable[[int], None]] = None
    ) -> int:
        target_host = urlparse(url).hostname
        await self.open(target_host=target_host)
        assert self.session is not None

        parsed_url = urlparse(url)
        referer = f"{parsed_url.scheme}://{parsed_url.netloc}/"
        headers = {
            "Range": f"bytes={start_byte}-{end_byte}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Referer": referer,
            "Sec-Ch-Ua": '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        }

        async def _do_stream(session_to_use: aiohttp.ClientSession) -> int:
            total_streamed = 0
            current_offset = start_byte
            async with session_to_use.get(url, headers=headers) as response:
                if response.status not in (200, 206):
                    raise RuntimeError(f"Server returned HTTP {response.status} for range request {start_byte}-{end_byte}")

                # Integrity guard: if requesting a non-zero range, server MUST return HTTP 206 Partial Content
                if start_byte > 0 and response.status == 200:
                    raise RuntimeError(
                        f"Server returned full content (HTTP 200) instead of partial content (HTTP 206) "
                        f"for requested range {start_byte}-{end_byte}."
                    )

                # Validate Content-Range header if present
                content_range = response.headers.get("Content-Range", "")
                if content_range and response.status == 206:
                    try:
                        # Format: "bytes <start>-<end>/<total>"
                        range_part = content_range.split(" ")[1].split("/")[0]
                        range_start = int(range_part.split("-")[0])
                        if range_start != start_byte:
                            raise RuntimeError(
                                f"Range mismatch: requested offset {start_byte} but server sent {range_start} ({content_range})"
                            )
                    except (IndexError, ValueError):
                        pass

                buffer_size = 256 * 1024  # 256 KB high-throughput streaming read buffer
                while not stop_event.is_set():
                    chunk = await response.content.read(buffer_size)
                    if not chunk:
                        break

                    chunk_len = len(chunk)
                    await write_callback(current_offset, chunk)
                    current_offset += chunk_len
                    total_streamed += chunk_len

                    # Record bandwidth metrics
                    bandwidth_monitor.record_bytes(self.interface_id, chunk_len)
                    if progress_callback:
                        progress_callback(chunk_len)

                    # Simulated network throttle
                    if self.is_simulated and simulation_manager.enabled:
                        await simulation_manager.throttle(self.interface_id, chunk_len)

            return total_streamed

        try:
            return await _do_stream(self.session)
        except (aiohttp.ClientError, ConnectionResetError, ConnectionError, OSError, asyncio.TimeoutError) as conn_err:
            # Only fall back to unbound if the OS actually rejected binding to this local IP address
            is_bind_rejection = False
            if isinstance(conn_err, OSError) and getattr(conn_err, "winerror", None) == 10049:
                is_bind_rejection = True
            elif "not valid in its context" in str(conn_err).lower() or "cannot assign requested address" in str(conn_err).lower():
                is_bind_rejection = True

            if self.is_bound and is_bind_rejection:
                logger.warning(
                    f"Interface {self.interface_id} IP binding ({self.local_ip}) rejected by OS ({conn_err}). "
                    f"Switching {self.interface_id} to unbound fallback connector."
                )
                self.binding_disabled = True
                self.is_bound = False
                await self.close()
                timeout = aiohttp.ClientTimeout(total=None, connect=15, sock_read=45)
                self.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=20), timeout=timeout)
                # Retry request via fallback connection
                return await _do_stream(self.session)
            raise
