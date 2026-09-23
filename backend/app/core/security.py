import ipaddress
import re
import socket
from urllib.parse import urlparse
from pathlib import Path
from typing import Tuple

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private
    ipaddress.ip_network("172.16.0.0/12"),    # Private
    ipaddress.ip_network("192.168.0.0/16"),   # Private
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / Cloud metadata (e.g. AWS/GCP 169.254.169.254)
    ipaddress.ip_network("0.0.0.0/8"),        # Current network
    ipaddress.ip_network("::1/128"),          # IPv6 Loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 Private ULA
    ipaddress.ip_network("fe80::/10"),        # IPv6 Link-local
]

INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_WIN_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def sanitize_filename(name: str, fallback: str = "download.bin") -> str:
    """
    Sanitize filename against directory traversal, control chars,
    and Windows reserved device names.
    """
    if not name:
        return fallback
    
    # Strip leading/trailing whitespaces and dots
    name = Path(name).name.strip(" .")
    
    # Remove invalid windows characters
    name = INVALID_WIN_CHARS.sub("_", name)
    
    # Avoid reserved Windows device names
    base_stem = Path(name).stem.upper()
    if base_stem in RESERVED_WIN_NAMES:
        name = f"_{name}"
        
    if not name:
        name = fallback
        
    # Cap length to 240 chars for NTFS safety
    if len(name) > 240:
        ext = Path(name).suffix
        stem = Path(name).stem[:240 - len(ext)]
        name = stem + ext
        
    return name

def validate_url(url_str: str, allow_private: bool = False) -> Tuple[bool, str]:
    """
    Validates scheme and guards against SSRF attacks.
    Returns (is_valid, error_message).
    """
    if not url_str:
        return False, "URL cannot be empty."
    
    try:
        parsed = urlparse(url_str.strip())
    except Exception as e:
        return False, f"Malformed URL: {e}"
        
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported scheme '{parsed.scheme}'. Only http:// and https:// are allowed."
        
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a valid hostname or IP."
        
    # If private networks are explicitly permitted by settings, bypass IP block check
    if allow_private:
        return True, ""
        
    # Direct hostname check for common loopbacks
    if hostname.lower() in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False, "Access to localhost or loopback is blocked for security (SSRF protection)."
        
    # Resolve hostname to verify IP
    try:
        # Check if already an IP
        ip_obj = ipaddress.ip_address(hostname)
        for net in BLOCKED_IP_NETWORKS:
            if ip_obj in net:
                return False, f"Access to private/local address {ip_obj} is blocked (SSRF protection)."
    except ValueError:
        # Hostname is a domain name, resolve it
        try:
            addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
            for family, socktype, proto, canonname, sockaddr in addr_info:
                resolved_ip = sockaddr[0]
                ip_obj = ipaddress.ip_address(resolved_ip)
                for net in BLOCKED_IP_NETWORKS:
                    if ip_obj in net:
                        return False, f"Domain {hostname} resolves to private IP {ip_obj}, which is blocked."
        except socket.gaierror:
            # Let the actual connection attempt handle DNS resolution failure gracefully
            pass
            
    return True, ""
