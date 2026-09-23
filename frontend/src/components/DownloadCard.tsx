import React from 'react';
import type { Download as DownloadType } from '../types';
import { 
  Play, 
  Pause, 
  X, 
  Trash2, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  HardDrive, 
  Gauge,
  ShieldCheck
} from 'lucide-react';
import { formatBytes, formatSpeed, formatETA } from '../services/api';

interface DownloadCardProps {
  download: DownloadType;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  onCancel: (id: string) => void;
  onDelete: (id: string) => void;
  onOpenDetails: (download: DownloadType) => void;
}

export const DownloadCard: React.FC<DownloadCardProps> = ({
  download,
  onPause,
  onResume,
  onCancel,
  onDelete,
  onOpenDetails
}) => {
  const percent = download.total_size > 0 
    ? Math.min(100, Math.round((download.downloaded_size / download.total_size) * 100))
    : 0;

  const getStatusBadge = () => {
    switch (download.status) {
      case 'DOWNLOADING':
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            Downloading
          </span>
        );
      case 'PAUSED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Paused
          </span>
        );
      case 'COMPLETED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            Completed
          </span>
        );
      case 'FAILED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-rose-400" />
            Failed
          </span>
        );
      case 'CANCELLED':
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
            Cancelled
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-800 text-slate-300">
            {download.status}
          </span>
        );
    }
  };

  return (
    <div 
      className="glass-panel-interactive rounded-2xl p-5 border border-slate-800 cursor-pointer"
      onClick={() => onOpenDetails(download)}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-slate-800/80 border border-slate-700/60 shrink-0">
            <HardDrive className="w-5 h-5 text-brand-cyan" />
          </div>
          <div>
            <h4 className="text-sm font-bold text-white tracking-tight truncate max-w-sm sm:max-w-md">
              {download.filename}
            </h4>
            <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-400">
              <span>{formatBytes(download.downloaded_size)} / {formatBytes(download.total_size)}</span>
              <span>•</span>
              <span>{download.chunks_completed} / {download.chunks_total} chunks</span>
              <span>•</span>
              <span className="font-mono text-slate-300">{download.mode}</span>
            </div>
          </div>
        </div>

        {/* Status & Actions */}
        <div className="flex items-center gap-2 self-end sm:self-auto" onClick={(e) => e.stopPropagation()}>
          {getStatusBadge()}

          {/* Action buttons */}
          {download.status === 'DOWNLOADING' && (
            <button
              onClick={() => onPause(download.id)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              title="Pause"
            >
              <Pause className="w-4 h-4 text-amber-400" />
            </button>
          )}

          {(download.status === 'PAUSED' || download.status === 'FAILED') && (
            <button
              onClick={() => onResume(download.id)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              title="Resume"
            >
              <Play className="w-4 h-4 text-emerald-400" />
            </button>
          )}

          {download.status !== 'COMPLETED' && download.status !== 'CANCELLED' && (
            <button
              onClick={() => onCancel(download.id)}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
              title="Cancel"
            >
              <X className="w-4 h-4 text-rose-400" />
            </button>
          )}

          {download.status === 'COMPLETED' && (
            <button
              onClick={() => onOpenDetails(download)}
              className="px-2.5 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition-colors flex items-center gap-1.5 text-xs font-medium"
              title="Verify File Integrity"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Verify Integrity</span>
            </button>
          )}

          <button
            onClick={() => onDelete(download.id)}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-900/40 text-slate-400 hover:text-rose-300 border border-slate-700 transition-colors"
            title="Delete Download Record"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5 mt-2">
        <div className="w-full h-2 bg-slate-800/80 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              download.status === 'COMPLETED'
                ? 'bg-emerald-500'
                : download.status === 'DOWNLOADING'
                ? 'bg-gradient-to-r from-blue-500 via-cyan-400 to-emerald-400'
                : download.status === 'FAILED'
                ? 'bg-rose-500'
                : 'bg-amber-500'
            }`}
            style={{ width: `${percent}%` }}
          />
        </div>

        {/* Telemetry Metrics */}
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono pt-1">
          <div className="flex items-center gap-4">
            <span className="text-slate-200 font-semibold">{percent}%</span>
            {download.status === 'DOWNLOADING' && (
              <span className="flex items-center gap-1 text-brand-cyan">
                <Gauge className="w-3.5 h-3.5" />
                {formatSpeed(download.current_speed_bps)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {download.status === 'DOWNLOADING' && (
              <span className="flex items-center gap-1 text-slate-300">
                <Clock className="w-3.5 h-3.5 text-slate-500" />
                ETA: {formatETA(download.eta_seconds)}
              </span>
            )}
            <span className="text-[11px] text-slate-500 underline decoration-slate-700">
              View Chunks
            </span>
          </div>
        </div>
      </div>

      {/* Error message snippet - only display when download is NOT completed */}
      {download.error_message && download.status !== 'COMPLETED' && (
        <div className="mt-2 text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-xl border border-rose-500/20 flex items-center justify-between gap-3">
          <div className="truncate flex-1">
            <span className="font-semibold block text-rose-300">Download Stalled</span>
            <span className="text-[11px] text-rose-400/90 truncate block">{download.error_message}</span>
          </div>
          <button
            onClick={() => onOpenDetails(download)}
            className="px-2.5 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 border border-rose-500/40 text-xs font-semibold whitespace-nowrap transition-all"
          >
            Update Link
          </button>
        </div>
      )}
    </div>
  );
};
