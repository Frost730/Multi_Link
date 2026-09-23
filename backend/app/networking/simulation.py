import asyncio
import time
from typing import List, Dict, Optional
from app.models.schemas import NetworkInterface, NetworkType

class SimulationManager:
    def __init__(self):
        self.enabled = False
        self._simulated_interfaces: Dict[str, NetworkInterface] = {
            "sim_ethernet": NetworkInterface(
                id="sim_ethernet",
                name="Simulated Gigabit Ethernet",
                description="Emulated High-Speed Wired Network",
                type=NetworkType.ETHERNET,
                status="connected",
                ipv4="192.168.1.150",
                speed_mbps=100,
                usable=True,
                is_enabled=True,
                is_simulated=True
            ),
            "sim_wifi": NetworkInterface(
                id="sim_wifi",
                name="Simulated Wi-Fi 6",
                description="Emulated 5GHz Wireless Connection",
                type=NetworkType.WIFI,
                status="connected",
                ipv4="192.168.2.175",
                speed_mbps=50,
                usable=True,
                is_enabled=True,
                is_simulated=True
            ),
            "sim_usb": NetworkInterface(
                id="sim_usb",
                name="Simulated USB Tethering",
                description="Emulated 5G Mobile Hotspot Link",
                type=NetworkType.USB_TETHER,
                status="connected",
                ipv4="192.168.42.129",
                speed_mbps=25,
                usable=True,
                is_enabled=True,
                is_simulated=True
            ),
        }
        # Artificial bandwidth speed caps (bytes per second)
        self.speed_caps: Dict[str, float] = {
            "sim_ethernet": 12.5 * 1024 * 1024,  # 100 Mbps = 12.5 MB/s
            "sim_wifi": 6.0 * 1024 * 1024,       # 48 Mbps = 6.0 MB/s
            "sim_usb": 2.5 * 1024 * 1024,        # 20 Mbps = 2.5 MB/s
        }
        # Artificial latencies
        self.latencies: Dict[str, float] = {
            "sim_ethernet": 10.0,
            "sim_wifi": 25.0,
            "sim_usb": 45.0,
        }

    def get_interfaces(self) -> List[NetworkInterface]:
        return list(self._simulated_interfaces.values())

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def set_interface_enabled(self, interface_id: str, enabled: bool) -> None:
        if interface_id in self._simulated_interfaces:
            self._simulated_interfaces[interface_id].is_enabled = enabled

    async def throttle(self, interface_id: str, chunk_bytes: int):
        """Simulate realistic bandwidth delay for the simulated interface."""
        if not self.enabled or interface_id not in self.speed_caps:
            return
        cap = self.speed_caps[interface_id]
        if cap > 0:
            target_delay = chunk_bytes / cap
            # Sleep in realistic bursts (cap delay per chunk write)
            await asyncio.sleep(min(target_delay, 0.2))

simulation_manager = SimulationManager()
