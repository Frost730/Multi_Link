import aiohttp
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple
from app.core.security import validate_url, sanitize_filename
from app.models.schemas import AnalyzeResponse, OperatingMode, NetworkInterface
from app.networking.interface_manager import interface_manager
from app.networking.simulation import simulation_manager
from app.core.config import settings
import logging

logger = logging.getLogger("multilink.metadata")

def extract_filename_from_headers(headers: dict, url: str) -> str:
    content_disp = headers.get("Content-Disposition", "")
    if content_disp:
        # Check for filename*=UTF-8''filename.ext (RFC 5987)
        if "filename*=" in content_disp:
            parts = content_disp.split("filename*=")
            if len(parts) > 1:
                val = parts[1].split(";")[0].strip("\"' ")
                if "''" in val:
                    _, encoded = val.split("''", 1)
                    return sanitize_filename(urllib.parse.unquote(encoded))
                return sanitize_filename(urllib.parse.unquote(val))
        # Check standard filename="file.ext"
        if "filename=" in content_disp:
            parts = content_disp.split("filename=")
            if len(parts) > 1:
                val = parts[1].split(";")[0].strip("\"' ")
                return sanitize_filename(urllib.parse.unquote(val))

    # Fallback to URL path
    parsed = urllib.parse.urlparse(url)
    path_name = Path(parsed.path).name
    if path_name:
        return sanitize_filename(urllib.parse.unquote(path_name))
        
    return "download.bin"

async def probe_url(url: str, allow_private: bool = False) -> AnalyzeResponse:
    is_valid, err = validate_url(url, allow_private=allow_private)
    if not is_valid:
        raise ValueError(err)

    parsed = urllib.parse.urlparse(url)
    is_https = parsed.scheme.lower() == "https"
    headers_req = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Referer": f"{parsed.scheme}://{parsed.netloc}/"
    }

    timeout = aiohttp.ClientTimeout(total=15, connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Step 1: HEAD request
        total_size = 0
        range_supported = False
        filename = "download.bin"
        mime_type = "application/octet-stream"
        server = None

        try:
            async with session.head(url, headers=headers_req, allow_redirects=True) as resp:
                headers = dict(resp.headers)
                server = headers.get("Server")
                mime_type = headers.get("Content-Type", "application/octet-stream").split(";")[0].strip()
                filename = extract_filename_from_headers(headers, str(resp.url))

                if "Content-Length" in headers:
                    try:
                        total_size = int(headers["Content-Length"])
                    except ValueError:
                        total_size = 0

                accept_ranges = headers.get("Accept-Ranges", "").lower()
                if "bytes" in accept_ranges:
                    range_supported = True
        except Exception as e:
            logger.debug(f"HEAD request failed, probing with GET range: {e}")

        # Step 2: Probing byte range with GET Range: bytes=0-0 to be 100% certain
        try:
            probe_headers = dict(headers_req)
            probe_headers["Range"] = "bytes=0-0"
            async with session.get(url, headers=probe_headers, allow_redirects=True) as resp:
                if resp.status == 206:
                    range_supported = True
                    content_range = resp.headers.get("Content-Range", "")
                    if "/" in content_range:
                        try:
                            total_size = int(content_range.split("/")[1].strip())
                        except ValueError:
                            pass
                if not filename or filename == "download.bin":
                    filename = extract_filename_from_headers(dict(resp.headers), str(resp.url))
                if not server:
                    server = resp.headers.get("Server")
                if not mime_type or mime_type == "application/octet-stream":
                    mime_type = resp.headers.get("Content-Type", mime_type).split(";")[0].strip()
        except Exception as e:
            logger.warning(f"Range probe error: {e}")

    # Determine interfaces available
    if simulation_manager.enabled:
        interfaces = simulation_manager.get_interfaces()
        active_mode = OperatingMode.SIMULATION_MODE
        mode_desc = "Simulation Mode Active — Distributing chunks across emulated Ethernet, Wi-Fi, and USB links."
    else:
        interfaces = interface_manager.get_interfaces()
        usable_interfaces = [i for i in interfaces if i.usable and i.status == "connected"]
        if not range_supported:
            active_mode = OperatingMode.SINGLE_CONNECTION
            mode_desc = "Server does not support HTTP Range requests — single-stream mode will be used."
        elif len(usable_interfaces) > 1:
            active_mode = OperatingMode.TRUE_MULTI_INTERFACE
            mode_desc = f"Multi-interface aggregation active across {len(usable_interfaces)} detected interfaces."
        else:
            active_mode = OperatingMode.MULTI_CONNECTION
            mode_desc = "Parallel multi-connection range mode active on available primary connection."

    return AnalyzeResponse(
        url=url,
        filename=filename,
        total_size=total_size,
        range_supported=range_supported,
        mime_type=mime_type,
        server=server,
        is_https=is_https,
        suggested_mode=active_mode,
        mode_description=mode_desc,
        available_interfaces=interfaces
    )
