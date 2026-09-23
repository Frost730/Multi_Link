from pathlib import Path
from pydantic import BaseModel, Field
import os

class Settings(BaseModel):
    app_name: str = "MultiLink"
    app_version: str = "1.0.0"
    host: str = "127.0.0.1"
    port: int = 8000
    
    # Storage
    base_dir: Path = Path(__file__).resolve().parent.parent.parent
    downloads_dir: Path = Path(os.path.expanduser("~")) / "Downloads" / "MultiLink"
    data_dir: Path = base_dir / "data"
    db_path: Path = data_dir / "multilink.db"
    
    # Download defaults
    default_chunk_size_bytes: int = 16 * 1024 * 1024  # 16 MB default
    min_chunk_size_bytes: int = 2 * 1024 * 1024       # 2 MB minimum
    max_chunk_size_bytes: int = 64 * 1024 * 1024      # 64 MB maximum
    max_concurrent_connections_per_download: int = 8
    max_global_concurrent_connections: int = 16
    max_retries_per_chunk: int = 5
    connection_timeout_seconds: int = 20
    read_timeout_seconds: int = 30
    
    # Security
    allow_private_network_downloads: bool = False
    allowed_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]
    
    # Simulation mode defaults
    simulation_mode_enabled: bool = False

settings = Settings()
settings.downloads_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
