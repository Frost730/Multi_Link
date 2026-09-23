import React, { useEffect, useState } from 'react';
import { 
  X, 
  Layers, 
  ShieldCheck, 
  Copy, 
  Check,
  RotateCcw,
  AlertTriangle
} from 'lucide-react';
import type { Download as DownloadType, Chunk } from '../types';
import { api, formatBytes, formatSpeed, formatETA } from '../services/api';

interface DownloadDetailModalProps {
  download: DownloadType | null;
  isOpen: boolean;
  onClose: () => void;
  onDownloadUpdated?: () => void;
}

export const DownloadDetailModal: React.FC<DownloadDetailModalProps> = ({
  download,
  isOpen,
  onClose,
  onDownloadUpdated
}) => {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [selectedChunk, setSelectedChunk] = useState<Chunk | null>(null);
  const [copiedSha, setCopiedSha] = useState(false);
  const [isEditingUrl, setIsEditingUrl] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [updatingUrl, setUpdatingUrl] = useState(false);
  const [retrying, setRetrying] = useState(false);

  useEffect(() => {
    if (isOpen && download?.error_message && (download.error_message.includes('expired') || download.error_message.includes('update the URL'))) {
      setIsEditingUrl(true);
    }
  }, [isOpen, download?.id, download?.error_message]);

  const checkUrlExpired = (urlStr: string): { expired: boolean; expiryDate?: Date } | null => {
    try {
      const parsed = new URL(urlStr);
      const eParam = parsed.searchParams.get('e') || parsed.searchParams.get('expires') || parsed.searchParams.get('Expires');
      if (eParam && /^\d+$/.test(eParam)) {
        const ts = parseInt(eParam, 10);
        return {
          expired: ts < (Date.now() / 1000),
          expiryDate: new Date(ts * 1000)
        };
      }
    } catch {}
    return null;
  };

  const handleUpdateUrl = async () => {
    if (!download || !newUrl.trim()) return;
    setUpdatingUrl(true);
    try {
      await api.updateDownloadUrl(download.id, newUrl.trim());
      setIsEditingUrl(false);
      setNewUrl('');
      onDownloadUpdated?.();
      const data = await api.getChunks(download.id);
      setChunks(data);
    } catch (err: any) {
      console.error('Failed to update download URL:', err);
      alert(err.message || 'Failed to update download URL');
    } finally {
      setUpdatingUrl(false);
    }
  };

  const handleRetryFailed = async () => {
    if (!download) return;
    setRetrying(true);
    try {
      await api.retryFailedChunks(download.id);
      onDownloadUpdated?.();
      const data = await api.getChunks(download.id);
      setChunks(data);
    } catch (err: any) {
      console.error('Failed to retry chunks:', err);
      alert(err.message || 'Failed to retry chunks');
    } finally {
      setRetrying(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !download) return;

    let intervalId: any;
    const fetchChunks = async () => {
      try {
        const data = await api.getChunks(download.id);
        setChunks(data);
      } catch (err) {
        console.error('Failed to fetch chunks:', err);
      }
    };

    fetchChunks();
    // Poll chunks every 1.5s if actively downloading
    if (download.status === 'DOWNLOADING') {
      intervalId = setInterval(fetchChunks, 1500);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [isOpen, download?.id, download?.status]);

  if (!isOpen || !download) return null;

  const handleCopySha = () => {
    if (download.checksum) {
      navigator.clipboard.writeText(download.checksum);
      setCopiedSha(true);
      setTimeout(() => setCopiedSha(false), 2000);
    }
  };

  const getChunkColor = (c: Chunk) => {
    switch (c.status) {
      case 'COMPLETED':
        return 'bg-emerald-500 hover:bg-emerald-400 border-emerald-400/50';
      case 'DOWNLOADING':
        return 'bg-cyan-500 animate-pulse border-cyan-300';
      case 'FAILED':
        return 'bg-rose-500 border-rose-400';
      case 'PENDING':
      default:
        return 'bg-slate-800 hover:bg-slate-700 border-slate-700';
    }
  };

  const completedCount = chunks.filter(c => c.status === 'COMPLETED').length;
  const downloadingCount = chunks.filter(c => c.status === 'DOWNLOADING').length;
  const pendingCount = chunks.filter(c => c.status === 'PENDING').length;
  const failedCount = chunks.filter(c => c.status === 'FAILED').length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-4xl rounded-2xl border border-slate-700/80 shadow-2xl overflow-hidden bg-dark-900 max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-500/10 text-brand-cyan border border-blue-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white truncate max-w-lg">
                {download.filename}
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                ID: {download.id} • Mode: {download.mode}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="p-6 space-y-6 overflow-y-auto">
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="p-3 rounded-xl bg-dark-950 border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Total File Size</span>
              <span className="font-mono font-bold text-white text-sm">
                {formatBytes(download.total_size)}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-dark-950 border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Downloaded</span>
              <span className="font-mono font-bold text-brand-cyan text-sm">
                {formatBytes(download.downloaded_size)}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-dark-950 border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Current Speed</span>
              <span className="font-mono font-bold text-emerald-400 text-sm">
                {formatSpeed(download.current_speed_bps)}
              </span>
            </div>
            <div className="p-3 rounded-xl bg-dark-950 border border-slate-800">
              <span className="text-slate-500 block text-[11px]">Estimated Remaining</span>
              <span className="font-mono font-bold text-slate-200 text-sm">
                {formatETA(download.eta_seconds)}
              </span>
            </div>
          </div>

          {/* Details Row: Save Path & Checksum */}
          <div className="p-4 rounded-xl bg-dark-950 border border-slate-800 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Save Destination:</span>
              <span className="font-mono text-slate-200 truncate max-w-md">{download.save_path}</span>
            </div>
            <div className="flex flex-col gap-1.5 pt-1 border-t border-slate-800/60">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Source URL:</span>
                <button
                  onClick={() => setIsEditingUrl(!isEditingUrl)}
                  className="text-[11px] text-brand-cyan hover:underline"
                >
                  {isEditingUrl ? 'Cancel' : 'Refresh/Update Link'}
                </button>
              </div>
              {isEditingUrl ? (
                <div className="space-y-1.5 mt-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="url"
                      value={newUrl}
                      onChange={(e) => setNewUrl(e.target.value)}
                      placeholder="Paste fresh download link from website..."
                      className="flex-1 bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white font-mono focus:outline-none focus:border-brand-blue"
                    />
                    <button
                      onClick={handleUpdateUrl}
                      disabled={updatingUrl || !newUrl.trim()}
                      className="px-3 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold disabled:opacity-50"
                    >
                      {updatingUrl ? 'Saving...' : 'Update & Resume'}
                    </button>
                  </div>
                  {newUrl && (() => {
                    const check = checkUrlExpired(newUrl);
                    if (check?.expired) {
                      return (
                        <div className="text-[11px] text-rose-300 bg-rose-500/15 border border-rose-500/30 rounded-lg p-2 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                          <span>This link already expired at {check.expiryDate?.toLocaleTimeString()}! Do not copy from browser history. Click "Download Now" on the webpage again to get a fresh link.</span>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>
              ) : (
                <div>
                  <span className="font-mono text-slate-400 truncate max-w-xl text-[11px] block">{download.url}</span>
                  {(() => {
                    const check = checkUrlExpired(download.url);
                    if (check?.expired) {
                      return (
                        <div className="text-[11px] text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-lg px-2 py-1 mt-1 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                          <span>Link token expired at {check.expiryDate?.toLocaleTimeString()}. Click "Refresh/Update Link" above to paste a fresh URL.</span>
                        </div>
                      );
                    }
                    return null;
                  })()}
                </div>
              )}
            </div>
            {download.checksum && (
              <div className="flex items-center justify-between pt-1 border-t border-slate-800/60">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  SHA-256 Checksum:
                </span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-emerald-400 text-[11px] truncate max-w-xs">
                    {download.checksum}
                  </span>
                  <button
                    onClick={handleCopySha}
                    className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
                    title="Copy Checksum"
                  >
                    {copiedSha ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Chunk Map Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-white flex items-center gap-2">
                  Chunk Segmentation Map
                  <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 font-mono">
                    {chunks.length} Chunks
                  </span>
                </h4>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-3 text-[11px]">
                <span className="flex items-center gap-1.5 text-slate-300">
                  <span className="w-2.5 h-2.5 rounded bg-emerald-500" /> {completedCount} Done
                </span>
                <span className="flex items-center gap-1.5 text-slate-300">
                  <span className="w-2.5 h-2.5 rounded bg-cyan-500 animate-pulse" /> {downloadingCount} Active
                </span>
                <span className="flex items-center gap-1.5 text-slate-400">
                  <span className="w-2.5 h-2.5 rounded bg-slate-800 border border-slate-700" /> {pendingCount} Pending
                </span>
                {failedCount > 0 && (
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 text-rose-400">
                      <span className="w-2.5 h-2.5 rounded bg-rose-500" /> {failedCount} Failed
                    </span>
                    <button
                      onClick={handleRetryFailed}
                      disabled={retrying}
                      className="px-2 py-0.5 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 text-[10px] font-semibold flex items-center gap-1 transition-all disabled:opacity-50"
                      title="Retry all failed chunks immediately"
                    >
                      <RotateCcw className={`w-3 h-3 ${retrying ? 'animate-spin' : ''}`} />
                      {retrying ? 'Retrying...' : 'Retry Failed'}
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Chunk Blocks Grid */}
            <div className="p-4 rounded-xl bg-dark-950 border border-slate-800">
              <div className="grid grid-cols-8 sm:grid-cols-12 md:grid-cols-16 lg:grid-cols-20 gap-1.5 max-h-48 overflow-y-auto p-1">
                {chunks.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => setSelectedChunk(c)}
                    className={`h-7 rounded border transition-all ${getChunkColor(c)} ${
                      selectedChunk?.id === c.id ? 'ring-2 ring-white scale-105 z-10' : ''
                    }`}
                    title={`Chunk #${c.chunk_index} (${c.status})`}
                  />
                ))}
              </div>
            </div>

            {/* Selected Chunk Inspector Card */}
            {selectedChunk ? (
              <div className="p-4 rounded-xl bg-dark-950/80 border border-blue-500/30 text-xs space-y-2 animate-in fade-in duration-150">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="font-bold text-white flex items-center gap-1.5">
                    Chunk #{selectedChunk.chunk_index} Details
                  </span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold ${
                    selectedChunk.status === 'COMPLETED' ? 'bg-emerald-500/20 text-emerald-400' :
                    selectedChunk.status === 'DOWNLOADING' ? 'bg-cyan-500/20 text-cyan-400' :
                    selectedChunk.status === 'FAILED' ? 'bg-rose-500/20 text-rose-400' :
                    'bg-slate-800 text-slate-400'
                  }`}>
                    {selectedChunk.status}
                  </span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] font-mono">
                  <div>
                    <span className="text-slate-500 block">Byte Range:</span>
                    <span className="text-slate-200">
                      {selectedChunk.start_byte.toLocaleString()} - {selectedChunk.end_byte.toLocaleString()}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Downloaded:</span>
                    <span className="text-slate-200">
                      {formatBytes(selectedChunk.downloaded_bytes)}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Assigned Interface:</span>
                    <span className="text-brand-cyan">
                      {selectedChunk.assigned_interface || 'Dynamic / Unassigned'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Retries:</span>
                    <span className="text-slate-200">
                      {selectedChunk.retry_count}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-center text-xs text-slate-500 py-1">
                Click any chunk box above to inspect its byte range, retry count, and interface routing.
              </p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-6 py-3 border-t border-slate-800 bg-dark-950 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
