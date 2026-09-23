import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from app.core.config import settings
import logging

logger = logging.getLogger("multilink.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS downloads (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    filename TEXT NOT NULL,
    save_path TEXT NOT NULL,
    total_size INTEGER DEFAULT 0,
    downloaded_size INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    checksum TEXT,
    etag TEXT,
    mime_type TEXT,
    range_supported INTEGER DEFAULT 1,
    mode TEXT NOT NULL,
    error_message TEXT,
    chunks_total INTEGER DEFAULT 0,
    chunks_completed INTEGER DEFAULT 0,
    selected_interfaces TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    download_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_byte INTEGER NOT NULL,
    end_byte INTEGER NOT NULL,
    downloaded_bytes INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    assigned_interface TEXT,
    retry_count INTEGER DEFAULT 0,
    speed_bps REAL DEFAULT 0.0,
    start_time REAL,
    completion_time REAL,
    updated_at TEXT,
    FOREIGN KEY(download_id) REFERENCES downloads(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_download ON chunks(download_id);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

async def init_db():
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()
    logger.info(f"Database initialized at {settings.db_path}")

@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db
