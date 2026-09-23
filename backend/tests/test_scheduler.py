import pytest
from app.models.schemas import NetworkInterface, NetworkType
from app.downloads.scheduler import DynamicScheduler
from app.networking.bandwidth_monitor import bandwidth_monitor

def test_scheduler_dynamic_selection():
    eth = NetworkInterface(id="eth", name="Ethernet", type=NetworkType.ETHERNET, usable=True, is_enabled=True)
    wifi = NetworkInterface(id="wifi", name="Wi-Fi", type=NetworkType.WIFI, usable=True, is_enabled=True)

    scheduler = DynamicScheduler([eth, wifi])

    # Record throughput: Ethernet is fast, Wi-Fi is slower
    bandwidth_monitor.record_bytes("eth", 10_000_000)
    bandwidth_monitor.record_bytes("wifi", 1_000_000)

    active_assignments = {}
    best = scheduler.select_best_interface(active_assignments)
    assert best in ("eth", "wifi")

    # If Ethernet has 5 active chunks and Wi-Fi has 0, scheduler should balance load to Wi-Fi
    active_assignments = {f"c{i}": "eth" for i in range(10)}
    best_balanced = scheduler.select_best_interface(active_assignments)
    assert best_balanced == "wifi"

def test_scheduler_failure_backoff():
    eth = NetworkInterface(id="eth", name="Ethernet", type=NetworkType.ETHERNET, usable=True, is_enabled=True)
    scheduler = DynamicScheduler([eth])

    assert scheduler.is_interface_healthy("eth") is True
    scheduler.record_interface_failure("eth")
    # Immediate retry should be in backoff
    assert scheduler.is_interface_healthy("eth") is False
