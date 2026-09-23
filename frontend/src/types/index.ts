export type DownloadStatus = 
  | 'QUEUED'
  | 'INITIALIZING'
  | 'DOWNLOADING'
  | 'PAUSED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type ChunkStatus = 
  | 'PENDING'
  | 'DOWNLOADING'
  | 'COMPLETED'
  | 'FAILED';

export type NetworkType = 
  | 'ethernet'
  | 'wifi'
  | 'usb_tether'
  | 'bluetooth'
  | 'vpn'
  | 'virtual'
  | 'unknown';

export type OperatingMode = 
  | 'TRUE_MULTI_INTERFACE'
  | 'MULTI_CONNECTION'
  | 'SINGLE_CONNECTION'
  | 'SIMULATION_MODE';

export interface NetworkInterface {
  id: string;
  name: string;
  description: string;
  type: NetworkType;
  status: 'connected' | 'disconnected';
  ipv4?: string;
  ipv6?: string;
  gateway?: string;
  mac_address?: string;
  speed_mbps: number;
  usable: boolean;
  is_enabled: boolean;
  current_speed_bps: number;
  bytes_downloaded: number;
  is_simulated: boolean;
}

export interface Chunk {
  id: string;
  download_id: string;
  chunk_index: number;
  start_byte: number;
  end_byte: number;
  downloaded_bytes: number;
  status: ChunkStatus;
  assigned_interface?: string;
  retry_count: number;
  speed_bps: number;
  start_time?: number;
  completion_time?: number;
  updated_at?: string;
}

export interface Download {
  id: string;
  url: string;
  filename: string;
  save_path: string;
  total_size: number;
  downloaded_size: number;
  status: DownloadStatus;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  checksum?: string;
  etag?: string;
  mime_type?: string;
  range_supported: boolean;
  mode: OperatingMode;
  error_message?: string;
  chunks_total: number;
  chunks_completed: number;
  current_speed_bps: number;
  average_speed_bps: number;
  eta_seconds?: number;
  selected_interfaces: string[];
}

export interface AnalyzeResponse {
  url: string;
  filename: string;
  total_size: number;
  range_supported: boolean;
  mime_type?: string;
  server?: string;
  is_https: boolean;
  suggested_mode: OperatingMode;
  mode_description: string;
  available_interfaces: NetworkInterface[];
}

export interface NetworkInfoResponse {
  mode: OperatingMode;
  mode_description: string;
  simulation_mode: boolean;
  combined_speed_bps: number;
  interfaces: NetworkInterface[];
}

export interface Settings {
  downloads_dir: string;
  default_chunk_size_mb: number;
  max_concurrent_connections: number;
  max_retries: number;
  allow_private_network_downloads: boolean;
  simulation_mode_enabled: boolean;
  verify_checksum: boolean;
}

export interface BandwidthTestResult {
  interface_id: string;
  interface_name: string;
  speed_mbps: number;
  latency_ms: number;
  success: boolean;
  error?: string;
}

export interface SpeedPoint {
  timestamp: number;
  timeLabel: string;
  combined_mbps: number;
  [key: string]: any; // per-interface mbps
}
