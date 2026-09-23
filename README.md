# MultiLink — Multi-Network Download Manager

> **"Download faster using every available connection."**

MultiLink is a Windows-first download manager featuring a modern web interface and an intelligent local agent that splits large HTTP downloads into ranges, dynamically distributing chunks across multiple network interfaces (Ethernet, Wi-Fi, USB/mobile tethering) according to real-time throughput.

---

## Technical Reality & Transparency

> [!IMPORTANT]
> **Multiple HTTP connections do not automatically guarantee aggregate bandwidth across physical network interfaces. True multi-interface operation depends on OS routing/interface binding and server behavior.**
>
> MultiLink does NOT perform fake network aggregation. It distinguishes between:
> - **A. Multiple Parallel HTTP Connections** (accelerating downloads on a single link)
> - **B. Actual Per-Interface Socket Binding** (routing connections out specific network adapters)
>
> Where technically supported on Windows, MultiLink binds sockets to the local IPv4 address associated with the chosen adapter (`source_address=(interface_ip, 0)`). If Windows routing table metrics force traffic through the default route, MultiLink detects the condition and accurately reports the mode as `MULTI_CONNECTION` rather than falsely claiming bonded throughput.

---

## Operating Modes

| Mode | Indicator | Description |
| :--- | :--- | :--- |
| **`TRUE_MULTI_INTERFACE`** | Emerald Badge | Multiple physical/virtual adapters with distinct local IPs are actively routing concurrent ranges. |
| **`MULTI_CONNECTION`** | Blue Badge | Single interface detected or fallback mode active. Accelerated parallel range downloading is in effect. |
| **`SINGLE_CONNECTION`** | Amber Badge | The remote server does not support HTTP Range requests (`Accept-Ranges: bytes`). Single-stream download is used. |
| **`SIMULATION_MODE`** | Violet Badge | Multi-interface emulation layer active for development and testing. Distinctly labeled to prevent confusion with real hardware. |

---

## Key Features

- **Windows Network Discovery:** Detects Ethernet, Wi-Fi, USB Tethering, VPN, and virtual adapters with link speed, IP, and operational status.
- **Dynamic Scheduler & Work Stealing:** Distributes chunks proportional to moving-average throughput. If an interface drops or slows down, remaining bytes are re-assigned to healthy connections without losing completed work.
- **Persistent Pause & Resume:** SQLite state tracking allows pausing, closing the application, restarting, and resuming from the exact unfinished byte offsets.
- **Streaming Sparse File Assembler:** Streams chunks directly to disk (`.multilink.part`) using sparse file seeking, avoiding RAM exhaustion even for 50 GB+ files.
- **File Integrity:** Verifies total size and calculates streaming SHA-256 before atomic renaming to the final file.
- **SSRF & Path Traversal Protection:** Blocks loopback, private RFC1918 subnets, and cloud metadata endpoints by default, and sanitizes filenames against Windows reserved names (`CON`, `PRN`, `AUX`, etc.).
- **Real-Time Telemetry:** WebSocket-powered dashboard featuring rolling multi-line throughput charts (Recharts) and an interactive chunk visualizer.

---

## Architecture

```
React Web Dashboard (127.0.0.1:5173)
       ↓  HTTP REST & WebSocket
FastAPI Local Agent (127.0.0.1:8000)
       ↓
MultiLink Download Engine (ChunkManager, Scheduler, Assembler)
       ↓
Windows Network Sockets (Local IP Binding / Fallback)
       ↓
Internet
```

---

## Prerequisites

- **Windows 10 / 11**
- **Python 3.11+**
- **Node.js 18+** & `npm`

---

## Quickstart

### 1. One-Click Launch (Windows)
Double-click `start_multilink.bat` (or run `./start_multilink.ps1` in PowerShell).
This automatically starts both the backend API and frontend dev server in separate windows.

- **Dashboard:** [http://127.0.0.1:5173](http://127.0.0.1:5173)
- **API Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Manual Startup

**Backend:**
```cmd
cd backend
python -m pip install fastapi uvicorn aiohttp httpx pydantic aiosqlite psutil pytest pytest-asyncio
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Frontend:**
```cmd
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 3. Build Standalone Desktop Executable (`MultiLink.exe`)

To compile MultiLink as a standalone Windows desktop app (requiring no Python or Node.js on end-user machines):

```cmd
python scripts/build_desktop.py
```

The output will be generated at `dist/MultiLink/MultiLink.exe`. Run `MultiLink.exe` to launch the native borderless application window.


---

## Running the Test Suite

Run the full automated test suite (including unit tests and the live HTTP range integration test):
```cmd
cd backend
python -m pytest -v
```

Tests include:
- `test_security_and_meta.py`: URL scheme validation, SSRF protection, Windows filename sanitization.
- `test_chunk_assembler.py`: Dynamic range chunking, out-of-order sparse assembly, SHA-256 verification.
- `test_persistence_resume.py`: SQLite download/chunk state persistence and pause/resume lifecycle.
- `test_scheduler.py`: Bandwidth-weighted interface scoring and exponential backoff.
- `test_integration_download.py`: End-to-end multi-chunk range download with SHA-256 integrity check against a live mock server.

---

## Safety & System Integrity

MultiLink is safe and easy to uninstall:
- **NO** permanent modifications to the Windows routing table.
- **NO** disabling of network adapters.
- **NO** DNS alterations or hosts file modifications.
- **NO** kernel drivers or packet interception software installed.
- Binds only to `127.0.0.1` locally with strict CORS rules.
