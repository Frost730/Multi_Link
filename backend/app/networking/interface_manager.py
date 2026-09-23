import psutil
import socket
import re
import sys
import time
import subprocess
from typing import List, Dict, Optional, Tuple
from app.models.schemas import NetworkInterface, NetworkType
import logging

logger = logging.getLogger("multilink.networking")

class InterfaceManager:
    def __init__(self):
        self._enabled_overrides: Dict[str, bool] = {}
        self._descriptions_cache: Dict[str, str] = {}
        self._last_desc_query_time: float = 0.0

    def classify_adapter(self, name: str, desc: str = "") -> NetworkType:
        combined = f"{name} {desc}".lower()
        
        # Virtual / VPN first to avoid misclassifying Virtual Wi-Fi or VPN Ethernet
        if any(term in combined for term in ["tailscale", "zerotier", "wireguard", "openvpn", "tap-", "tun", "nordvpn", "expressvpn", "vpn"]):
            return NetworkType.VPN
        if any(term in combined for term in ["vethernet", "hyper-v", "vmware", "virtualbox", "vbox", "loopback", "wsl"]):
            return NetworkType.VIRTUAL
        if any(term in combined for term in ["bluetooth", "bth"]):
            return NetworkType.BLUETOOTH
        if any(term in combined for term in ["rndis", "tether", "usb ethernet", "remote ndis", "ncm", "cellular", "mobile"]):
            return NetworkType.USB_TETHER
        if any(term in combined for term in ["wi-fi", "wifi", "wlan", "wireless", "802.11", "mediatek"]):
            return NetworkType.WIFI
        if any(term in combined for term in ["ethernet", "lan", "realtek", "intel", "gigabit", "gbe", "broadcom", "killer", "pcie", "family controller", "nic"]):
            return NetworkType.ETHERNET
            
        return NetworkType.UNKNOWN

    def get_windows_adapter_descriptions(self) -> Dict[str, str]:
        """Query adapter descriptions via PowerShell Get-NetAdapter when on Windows."""
        now = time.time()
        if self._descriptions_cache and (now - self._last_desc_query_time < 60.0):
            return self._descriptions_cache

        descriptions = {}
        try:
            cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", "Get-NetAdapter | Select-Object -Property Name, InterfaceDescription | ConvertTo-Json"]
            
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                data = json.loads(proc.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    name = item.get("Name")
                    desc = item.get("InterfaceDescription", "")
                    if name:
                        descriptions[name] = desc
                self._descriptions_cache = descriptions
                self._last_desc_query_time = now
        except Exception as e:
            logger.debug(f"Could not query Get-NetAdapter descriptions: {e}")
            
        return self._descriptions_cache or descriptions

    def get_interfaces(self) -> List[NetworkInterface]:
        interfaces: List[NetworkInterface] = []
        descriptions = self.get_windows_adapter_descriptions()
        
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for name, addr_list in addrs.items():
            # Skip loopbacks
            if name.lower().startswith("loopback") or "pseudo" in name.lower():
                continue
                
            stat = stats.get(name)
            is_up = stat.isup if stat else False
            speed_mbps = stat.speed if stat and stat.speed > 0 else 0
            
            ipv4: Optional[str] = None
            ipv6: Optional[str] = None
            mac: Optional[str] = None

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    # Ignore loopback (127.x.x.x) and link-local / APIPA (169.254.x.x)
                    if not addr.address.startswith("127.") and not addr.address.startswith("169.254."):
                        ipv4 = addr.address
                elif addr.family == socket.AF_INET6:
                    if not addr.address.startswith("::1") and not addr.address.startswith("fe80"):
                        ipv6 = addr.address
                elif getattr(psutil, "AF_LINK", None) and addr.family == psutil.AF_LINK:
                    mac = addr.address

            desc = descriptions.get(name, "")
            adapter_type = self.classify_adapter(name, desc)
            
            # Connected condition: Has an active routable IPv4 address and is not down
            is_connected = (ipv4 is not None) and (is_up or stat is None)
            # Usable condition: Any connected interface with valid IPv4 (excluding bluetooth)
            is_usable = is_connected and (adapter_type != NetworkType.BLUETOOTH)
            
            # Clean sanitized ID
            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
            
            is_enabled = self._enabled_overrides.get(safe_id, True)

            interfaces.append(NetworkInterface(
                id=safe_id,
                name=name,
                description=desc,
                type=adapter_type,
                status="connected" if is_connected else "disconnected",
                ipv4=ipv4,
                ipv6=ipv6,
                mac_address=mac,
                speed_mbps=speed_mbps,
                usable=is_usable,
                is_enabled=is_enabled,
                is_simulated=False
            ))
            
        return interfaces

    def set_interface_enabled(self, interface_id: str, enabled: bool) -> None:
        self._enabled_overrides[interface_id] = enabled

    def reset_enabled_overrides(self) -> None:
        """Resets all interface overrides to enabled by default."""
        self._enabled_overrides.clear()

    def test_interface_socket_binding(self, local_ip: str, target_host: str = "1.1.1.1", target_port: int = 80, timeout: float = 3.0) -> Tuple[bool, float, Optional[str]]:
        """
        Attempts to bind a raw socket to (local_ip, 0) and connect to target.
        Measures round-trip TCP handshake latency.
        """
        import time
        start = time.perf_counter()
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.bind((local_ip, 0))
            sock.connect((target_host, target_port))
            latency = (time.perf_counter() - start) * 1000.0
            return True, latency, None
        except Exception as e:
            return False, 0.0, str(e)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

interface_manager = InterfaceManager()
