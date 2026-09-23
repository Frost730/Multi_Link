import type {
  Download,
  Chunk,
  AnalyzeResponse,
  NetworkInfoResponse,
  Settings,
  BandwidthTestResult
} from '../types';

const API_BASE = (typeof window !== 'undefined' && window.location.port !== '5173' && window.location.origin.startsWith('http'))
  ? window.location.origin
  : 'http://127.0.0.1:8000';
const WS_BASE = API_BASE.replace(/^http/, 'ws');

export const api = {
  async analyzeUrl(url: string): Promise<AnalyzeResponse> {
    const res = await fetch(`${API_BASE}/api/downloads/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Analysis failed' }));
      throw new Error(err.detail || 'Failed to analyze URL');
    }
    return res.json();
  },

  async createDownload(payload: {
    url: string;
    filename?: string;
    save_path?: string;
    selected_interfaces?: string[];
    custom_chunk_size_mb?: number;
  }): Promise<Download> {
    const res = await fetch(`${API_BASE}/api/downloads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to create download' }));
      throw new Error(err.detail || 'Failed to start download');
    }
    return res.json();
  },

  async getDownloads(): Promise<Download[]> {
    const res = await fetch(`${API_BASE}/api/downloads`);
    if (!res.ok) throw new Error('Failed to fetch downloads');
    return res.json();
  },

  async getDownload(id: string): Promise<Download> {
    const res = await fetch(`${API_BASE}/api/downloads/${id}`);
    if (!res.ok) throw new Error('Failed to fetch download details');
    return res.json();
  },

  async getChunks(id: string): Promise<Chunk[]> {
    const res = await fetch(`${API_BASE}/api/downloads/${id}/chunks`);
    if (!res.ok) throw new Error('Failed to fetch chunks');
    return res.json();
  },

  async pauseDownload(id: string): Promise<void> {
    await fetch(`${API_BASE}/api/downloads/${id}/pause`, { method: 'POST' });
  },

  async resumeDownload(id: string): Promise<void> {
    await fetch(`${API_BASE}/api/downloads/${id}/resume`, { method: 'POST' });
  },

  async cancelDownload(id: string): Promise<void> {
    await fetch(`${API_BASE}/api/downloads/${id}/cancel`, { method: 'POST' });
  },

  async deleteDownload(id: string, deleteFile = false): Promise<void> {
    await fetch(`${API_BASE}/api/downloads/${id}?delete_file=${deleteFile}`, { method: 'DELETE' });
  },

  async updateDownloadUrl(id: string, url: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/downloads/${id}/update-url`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to update URL' }));
      throw new Error(err.detail || 'Failed to update URL');
    }
  },

  async retryFailedChunks(id: string): Promise<void> {
    const res = await fetch(`${API_BASE}/api/downloads/${id}/retry-failed`, {
      method: 'POST'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Failed to retry chunks' }));
      throw new Error(err.detail || 'Failed to retry chunks');
    }
  },

  async getNetworkInfo(): Promise<NetworkInfoResponse> {
    const res = await fetch(`${API_BASE}/api/network/interfaces`);
    if (!res.ok) throw new Error('Failed to fetch network information');
    return res.json();
  },

  async getTelemetry(): Promise<{
    timestamp: number;
    combined_bps: number;
    interfaces: Record<string, number>;
    history: Array<{ timestamp: number; combined_bps: number; interfaces: Record<string, number> }>;
  }> {
    const res = await fetch(`${API_BASE}/api/network/telemetry`);
    if (!res.ok) throw new Error('Failed to fetch network telemetry');
    return res.json();
  },

  async toggleInterface(interfaceId: string, enabled: boolean): Promise<void> {
    await fetch(`${API_BASE}/api/network/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interface_id: interfaceId, enabled })
    });
  },

  async toggleSimulation(enabled: boolean): Promise<void> {
    await fetch(`${API_BASE}/api/network/simulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
  },

  async testBandwidth(interfaceId: string): Promise<BandwidthTestResult> {
    const res = await fetch(`${API_BASE}/api/network/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interface_id: interfaceId })
    });
    if (!res.ok) throw new Error('Bandwidth test request failed');
    return res.json();
  },

  async getSettings(): Promise<Settings> {
    const res = await fetch(`${API_BASE}/api/settings`);
    if (!res.ok) throw new Error('Failed to fetch settings');
    return res.json();
  },

  async updateSettings(settings: Settings): Promise<Settings> {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error('Failed to update settings');
    return res.json();
  }
};

export function connectWebSocket(onMessage: (event: any) => void): () => void {
  let ws: WebSocket | null = null;
  let reconnectTimer: any = null;
  let isClosed = false;

  function connect() {
    if (isClosed) return;
    ws = new WebSocket(`${WS_BASE}/ws/downloads`);

    ws.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        onMessage(parsed);
      } catch (err) {
        console.error('Error parsing WS message:', err);
      }
    };

    ws.onclose = () => {
      if (!isClosed) {
        reconnectTimer = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  }

  connect();

  return () => {
    isClosed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) ws.close();
  };
}

export function formatBytes(bytes: number, decimals = 2): string {
  if (bytes <= 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function formatSpeed(bitsPerSec: number): string {
  if (!bitsPerSec || bitsPerSec <= 0) return '0.0 Mbps';
  const mbps = bitsPerSec / 1_000_000.0;
  if (mbps >= 1000) {
    return `${(mbps / 1000).toFixed(2)} Gbps`;
  }
  return `${mbps.toFixed(1)} Mbps`;
}

export function formatETA(seconds?: number): string {
  if (seconds === undefined || seconds === null || !isFinite(seconds) || seconds <= 0) {
    return '--';
  }
  if (seconds < 60) {
    return `${Math.round(seconds)}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) {
    return `${mins}m ${secs}s`;
  }
  const hours = Math.floor(mins / 60);
  const remMins = mins % 60;
  return `${hours}h ${remMins}m`;
}
