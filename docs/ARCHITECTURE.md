# MultiLink Architecture Specification

## 1. System Topology

```
┌─────────────────────────────────────────────────────────────┐
│                 React Web Dashboard                         │
│  (Vite + TypeScript + Tailwind CSS + Lucide + Recharts)     │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST & WebSocket (127.0.0.1:8000)
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Local Agent                      │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │  DownloadManager  ◄──►  Scheduler  ◄──►  BandwidthMon   │ │
│ │        │                     │                          │ │
│ │        ▼                     ▼                          │ │
│ │   ChunkManager        ConnectionManager                 │ │
│ │        │                     │                          │ │
│ │        ▼                     ▼                          │ │
│ │   FileAssembler       InterfaceManager (psutil/Win32)   │ │
│ │        │                     │                          │ │
│ │        ▼                     ▼                          │ │
│ │ SQLite Persistence   Socket / TCPConnector Per Interface│ │
│ └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP Range Requests
                               ▼
                    Windows Network Adapters
                (Ethernet / Wi-Fi / USB Tether)
                               │
                               ▼
                            Internet
```

## 2. Core Components

### DownloadManager
The master lifecycle state machine coordinating download jobs across states:
- `QUEUED`: Enqueued in database and awaiting execution slot.
- `INITIALIZING`: Probing metadata, generating chunks, pre-allocating sparse file.
- `DOWNLOADING`: Active workers streaming ranges concurrently.
- `PAUSED`: Workers cancelled cleanly, unfinished bytes preserved.
- `COMPLETED`: Size validated, SHA-256 calculated, `.multilink.part` atomically renamed to target file.
- `FAILED`: Unrecoverable errors recorded with actionable user messages.
- `CANCELLED`: Interrupted by user and cleaned up.

### DynamicScheduler & Work Stealing
Instead of static ratios (e.g. 50% Ethernet, 30% Wi-Fi, 20% USB), the scheduler calculates a dynamic performance score for each healthy interface:
$$\text{Score} = \frac{\text{Throughput}_{\text{Mbps}} + 5.0}{\text{ActiveWorkers} + 1}$$

- **Throughput Weighting:** Faster interfaces finish chunks quicker and immediately pull the next pending chunk from the queue.
- **Work Stealing:** If an interface stalls or encounters a connection drop, its in-progress chunk is reclaimed. Its offset is adjusted to resume from `start_byte + downloaded_bytes`, allowing an available healthy connection to finish the chunk without discarding downloaded data.
- **Exponential Backoff:** Temporary errors back off with $2^{\text{retry\_count}}$ delay before re-enqueuing.

### Windows Interface Discovery & Binding
- Adapters are detected using `psutil.net_if_addrs`, `psutil.net_if_stats`, and PowerShell adapter queries.
- Classified into normalized categories: `ethernet`, `wifi`, `usb_tether`, `bluetooth`, `vpn`, `virtual`, `unknown`.
- `NetworkConnection` binds sockets via `local_addr=(interface_ip, 0)` on `aiohttp.TCPConnector`.
- Transparent fallback: If an OS routing conflict occurs, MultiLink falls back to an unbound connection and transparently informs the UI without exaggerating bonded network performance.

### Sparse Streamed FileAssembler & Integrity
- Large files (100MB to 50GB+) are streamed directly to disk into `<filename>.multilink.part`.
- Non-blocking thread-pool seeks write data directly at chunk byte offsets, preventing RAM bloat.
- On completion, `IntegrityManager` checks file size, calculates streaming SHA-256 in 4MB blocks, and atomically replaces the destination file.
