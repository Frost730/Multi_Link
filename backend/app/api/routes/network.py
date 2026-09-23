from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from pydantic import BaseModel

from app.models.schemas import NetworkInterface, BandwidthTestResponse, OperatingMode
from app.networking.interface_manager import interface_manager
from app.networking.simulation import simulation_manager
from app.networking.bandwidth_monitor import bandwidth_monitor

router = APIRouter(prefix="/api/network", tags=["Network"])

class ToggleInterfaceRequest(BaseModel):
    interface_id: str
    enabled: bool

class SimulationToggleRequest(BaseModel):
    enabled: bool

class BandwidthTestRequest(BaseModel):
    interface_id: str

@router.get("/telemetry")
async def get_telemetry_endpoint():
    point = bandwidth_monitor.tick_history()
    return {
        "timestamp": point.timestamp,
        "combined_bps": point.combined_bps,
        "interfaces": point.interfaces,
        "history": [p.model_dump() for p in bandwidth_monitor.get_history()]
    }

@router.get("/interfaces")
async def get_interfaces_endpoint():
    if simulation_manager.enabled:
        interfaces = simulation_manager.get_interfaces()
        mode = OperatingMode.SIMULATION_MODE
        mode_desc = "Simulation Mode Active — Multiple networks emulated for testing."
    else:
        all_interfaces = interface_manager.get_interfaces()
        interfaces = [i for i in all_interfaces if i.status == "connected" and i.ipv4 and i.usable and not i.ipv4.startswith("169.254.")]
        if len(interfaces) > 1:
            mode = OperatingMode.TRUE_MULTI_INTERFACE
            mode_desc = f"True Multi-Interface aggregation across {len(interfaces)} active physical/virtual adapters."
        elif len(interfaces) == 1:
            mode = OperatingMode.MULTI_CONNECTION
            mode_desc = "Single active interface detected — Multi-connection parallel range acceleration active."
        else:
            mode = OperatingMode.SINGLE_CONNECTION
            mode_desc = "No active network connections detected."

    # Merge real-time speed
    speeds = bandwidth_monitor.get_all_interface_speeds()
    for iface in interfaces:
        iface.current_speed_bps = speeds.get(iface.id, 0.0)

    return {
        "mode": mode,
        "mode_description": mode_desc,
        "simulation_mode": simulation_manager.enabled,
        "combined_speed_bps": bandwidth_monitor.get_combined_speed(),
        "interfaces": interfaces
    }

@router.post("/toggle")
async def toggle_interface_endpoint(req: ToggleInterfaceRequest):
    if simulation_manager.enabled:
        simulation_manager.set_interface_enabled(req.interface_id, req.enabled)
    else:
        interface_manager.set_interface_enabled(req.interface_id, req.enabled)
    return {"status": "ok", "interface_id": req.interface_id, "enabled": req.enabled}

@router.post("/simulation")
async def toggle_simulation_endpoint(req: SimulationToggleRequest):
    simulation_manager.set_enabled(req.enabled)
    return {"status": "ok", "simulation_enabled": simulation_manager.enabled}

@router.post("/test", response_model=BandwidthTestResponse)
async def test_interface_endpoint(req: BandwidthTestRequest):
    if simulation_manager.enabled:
        speed_cap = simulation_manager.speed_caps.get(req.interface_id, 50.0 * 1024 * 1024 / 8)
        speed_mbps = (speed_cap * 8.0) / 1_000_000.0
        latency = simulation_manager.latencies.get(req.interface_id, 20.0)
        return BandwidthTestResponse(
            interface_id=req.interface_id,
            interface_name=req.interface_id,
            speed_mbps=round(speed_mbps, 1),
            latency_ms=latency,
            success=True
        )

    all_ifaces = interface_manager.get_interfaces()
    target = next((i for i in all_ifaces if i.id == req.interface_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Interface not found")
    if not target.ipv4:
        return BandwidthTestResponse(
            interface_id=req.interface_id,
            interface_name=target.name,
            speed_mbps=0.0,
            latency_ms=0.0,
            success=False,
            error="Interface does not have a valid IPv4 address assigned"
        )

    success, latency, err = interface_manager.test_interface_socket_binding(target.ipv4)
    speed_mbps = float(target.speed_mbps) if target.speed_mbps > 0 else (100.0 if success else 0.0)

    return BandwidthTestResponse(
        interface_id=target.id,
        interface_name=target.name,
        speed_mbps=speed_mbps,
        latency_ms=round(latency, 2),
        success=success,
        error=err
    )
