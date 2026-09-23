from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DownloadStatus(str, Enum):
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    DOWNLOADING = "DOWNLOADING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class ChunkStatus(str, Enum):
    PENDING = "PENDING"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class NetworkType(str, Enum):
    ETHERNET = "ethernet"
    WIFI = "wifi"
    USB_TETHER = "usb_tether"
    BLUETOOTH = "bluetooth"
    VPN = "vpn"
    VIRTUAL = "virtual"
    UNKNOWN = "unknown"

class OperatingMode(str, Enum):
    TRUE_MULTI_INTERFACE = "TRUE_MULTI_INTERFACE"
    MULTI_CONNECTION = "MULTI_CONNECTION"
    SINGLE_CONNECTION = "SINGLE_CONNECTION"
    SIMULATION_MODE = "SIMULATION_MODE"

class NetworkInterface(BaseModel):
    id: str
    name: str
    description: str = ""
    type: NetworkType = NetworkType.UNKNOWN
    status: str = "disconnected"  # "connected" | "disconnected"
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    gateway: Optional[str] = None
    mac_address: Optional[str] = None
    speed_mbps: int = 0
    usable: bool = False
    is_enabled: bool = True
    current_speed_bps: float = 0.0
    bytes_downloaded: int = 0
    is_simulated: bool = False

class Chunk(BaseModel):
    id: str
    download_id: str
    chunk_index: int
    start_byte: int
    end_byte: int
    downloaded_bytes: int = 0
    status: ChunkStatus = ChunkStatus.PENDING
    assigned_interface: Optional[str] = None
    retry_count: int = 0
    speed_bps: float = 0.0
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    updated_at: Optional[str] = None

class Download(BaseModel):
    id: str
    url: str
    filename: str
    save_path: str
    total_size: int = 0
    downloaded_size: int = 0
    status: DownloadStatus = DownloadStatus.QUEUED
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    checksum: Optional[str] = None
    etag: Optional[str] = None
    mime_type: Optional[str] = None
    range_supported: bool = True
    mode: OperatingMode = OperatingMode.MULTI_CONNECTION
    error_message: Optional[str] = None
    chunks_total: int = 0
    chunks_completed: int = 0
    current_speed_bps: float = 0.0
    average_speed_bps: float = 0.0
    eta_seconds: Optional[float] = None
    selected_interfaces: List[str] = Field(default_factory=list)

class AnalyzeRequest(BaseModel):
    url: str

class AnalyzeResponse(BaseModel):
    url: str
    filename: str
    total_size: int
    range_supported: bool
    mime_type: Optional[str] = None
    server: Optional[str] = None
    is_https: bool = False
    suggested_mode: OperatingMode
    mode_description: str
    available_interfaces: List[NetworkInterface]

class DownloadCreate(BaseModel):
    url: str
    filename: Optional[str] = None
    save_path: Optional[str] = None
    selected_interfaces: Optional[List[str]] = None
    custom_chunk_size_mb: Optional[int] = None

class SettingsModel(BaseModel):
    downloads_dir: str
    default_chunk_size_mb: int = 16
    max_concurrent_connections: int = 8
    max_retries: int = 5
    allow_private_network_downloads: bool = False
    simulation_mode_enabled: bool = False
    verify_checksum: bool = True

class BandwidthTestResponse(BaseModel):
    interface_id: str
    interface_name: str
    speed_mbps: float
    latency_ms: float
    success: bool
    error: Optional[str] = None

class SpeedHistoryPoint(BaseModel):
    timestamp: float
    combined_bps: float
    interfaces: Dict[str, float] = Field(default_factory=dict)
