import React, { useState, useEffect } from 'react';
import { 
  X, 
  Search, 
  Download as DownloadIcon, 
  CheckCircle2, 
  AlertCircle, 
  HardDrive, 
  Network as NetworkIcon,
  Sliders,
  ArrowRight
} from 'lucide-react';
import type { AnalyzeResponse } from '../types';
import { api, formatBytes } from '../services/api';

interface NewDownloadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDownloadStarted: () => void;
  defaultDownloadsDir: string;
}

export const NewDownloadModal: React.FC<NewDownloadModalProps> = ({
  isOpen,
  onClose,
  onDownloadStarted,
  defaultDownloadsDir
}) => {
  const [url, setUrl] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [customFilename, setCustomFilename] = useState('');
  const [savePath, setSavePath] = useState(defaultDownloadsDir);
  const [selectedInterfaces, setSelectedInterfaces] = useState<string[]>([]);
  const [chunkSizeMb, setChunkSizeMb] = useState<number>(16);
  const [error, setError] = useState<string | null>(null);

  const resetState = () => {
    setUrl('');
    setAnalyzing(false);
    setStarting(false);
    setAnalysis(null);
    setCustomFilename('');
    setSavePath(defaultDownloadsDir);
    setSelectedInterfaces([]);
    setChunkSizeMb(16);
    setError(null);
  };

  useEffect(() => {
    if (!isOpen) {
      resetState();
    }
  }, [isOpen, defaultDownloadsDir]);

  const handleClose = () => {
    resetState();
    onClose();
  };

  if (!isOpen) return null;

  const handleAnalyze = async () => {
    if (!url.trim()) return;
    setAnalyzing(true);
    setError(null);
    setAnalysis(null);

    try {
      const res = await api.analyzeUrl(url.trim());
      setAnalysis(res);
      setCustomFilename(res.filename);
      // Select all connected usable interfaces by default
      const defaultIds = res.available_interfaces
        .filter(i => i.usable && i.status === 'connected')
        .map(i => i.id);
      setSelectedInterfaces(defaultIds);
    } catch (err: any) {
      setError(err.message || 'Failed to analyze URL.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleStartDownload = async () => {
    if (!analysis) return;
    setStarting(true);
    setError(null);

    try {
      await api.createDownload({
        url: analysis.url,
        filename: customFilename.trim() || analysis.filename,
        save_path: savePath.trim() || defaultDownloadsDir,
        selected_interfaces: selectedInterfaces,
        custom_chunk_size_mb: chunkSizeMb
      });
      onDownloadStarted();
      handleClose();
    } catch (err: any) {
      setError(err.message || 'Failed to start download.');
    } finally {
      setStarting(false);
    }
  };

  const toggleInterfaceSelect = (id: string) => {
    setSelectedInterfaces(prev => 
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
    );
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) handleClose();
      }}
    >
      <div className="glass-panel w-full max-w-2xl rounded-2xl border border-slate-700/80 shadow-2xl overflow-hidden bg-dark-900">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-500/10 text-brand-cyan border border-blue-500/20">
              <DownloadIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Start New Download</h3>
              <p className="text-xs text-slate-400">MultiLink Intelligent Acceleration</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          {/* URL Input Bar */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-2">
              Download File URL (HTTP / HTTPS)
            </label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="url"
                  placeholder="https://example.com/largefile.iso"
                  value={url}
                  onChange={(e) => {
                    setUrl(e.target.value);
                    if (analysis) setAnalysis(null);
                    if (error) setError(null);
                  }}
                  onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
                  className="w-full bg-dark-950 border border-slate-800 focus:border-brand-blue rounded-xl pl-4 pr-9 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-brand-blue transition-all"
                />
                {url && (
                  <button
                    type="button"
                    onClick={() => {
                      setUrl('');
                      setAnalysis(null);
                      setError(null);
                    }}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 p-0.5 rounded transition-colors"
                    title="Clear URL"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
              <button
                onClick={handleAnalyze}
                disabled={analyzing || !url.trim()}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs border border-slate-700 transition-all disabled:opacity-50"
              >
                {analyzing ? (
                  <>
                    <span className="w-4 h-4 border-2 border-slate-400 border-t-white rounded-full animate-spin" />
                    <span>Analyzing...</span>
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4 text-brand-cyan" />
                    <span>Analyze URL</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Error Banner */}
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Analysis Result Card */}
          {analysis && (
            <div className="space-y-4 animate-in fade-in duration-300">
              <div className="p-4 rounded-xl bg-dark-950 border border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800/80">
                  <div className="flex items-center gap-2">
                    <HardDrive className="w-4 h-4 text-brand-cyan" />
                    <span className="text-xs font-semibold text-slate-300">File Analysis</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {analysis.range_supported ? (
                      <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1 font-medium">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Multi-Connection Supported
                      </span>
                    ) : (
                      <span className="text-xs px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1 font-medium">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Single-Stream Only (No Range)
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Size:</span>
                    <span className="font-mono text-slate-200 font-semibold">
                      {analysis.total_size > 0 ? formatBytes(analysis.total_size) : 'Unknown (Stream)'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Server:</span>
                    <span className="font-mono text-slate-200 truncate block">
                      {analysis.server || 'Standard Web Server'}
                    </span>
                  </div>
                </div>

                {/* Operating Mode Guidance */}
                <div className="p-2.5 rounded-lg bg-blue-500/5 border border-blue-500/15 text-xs text-blue-300">
                  <div className="font-semibold text-white mb-0.5">Mode: {analysis.suggested_mode}</div>
                  <div className="text-[11px] text-slate-300">{analysis.mode_description}</div>
                </div>
              </div>

              {/* Filename & Path Customization */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Save Filename</label>
                  <input
                    type="text"
                    value={customFilename}
                    onChange={(e) => setCustomFilename(e.target.value)}
                    className="w-full bg-dark-950 border border-slate-800 focus:border-brand-blue rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Download Folder</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={savePath}
                      onChange={(e) => setSavePath(e.target.value)}
                      className="w-full bg-dark-950 border border-slate-800 focus:border-brand-blue rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* Network Selection Checklist */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <NetworkIcon className="w-3.5 h-3.5 text-brand-cyan" />
                    Target Network Interfaces
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {selectedInterfaces.length} of {analysis.available_interfaces.filter(i => i.usable && i.status === 'connected').length} active
                  </span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {analysis.available_interfaces
                    .filter(i => i.usable && i.status === 'connected')
                    .map((iface) => {
                    const isSelected = selectedInterfaces.includes(iface.id);
                    return (
                      <div
                        key={iface.id}
                        onClick={() => toggleInterfaceSelect(iface.id)}
                        className={`p-3 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                          isSelected
                            ? 'bg-blue-600/10 border-blue-500/40 text-white'
                            : 'bg-dark-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        <div>
                          <div className="text-xs font-semibold flex items-center gap-1.5">
                            {iface.name}
                            {iface.is_simulated && (
                              <span className="text-[8px] px-1 py-0.2 rounded bg-violet-500/20 text-violet-300 uppercase font-mono">
                                SIM
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-slate-400 font-mono">
                            {iface.ipv4 || iface.type}
                          </div>
                        </div>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="rounded text-brand-blue focus:ring-0 cursor-pointer"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Chunk Size Configuration */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-slate-800 text-xs">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <Sliders className="w-3.5 h-3.5 text-brand-cyan" />
                  Chunk Size:
                </span>
                <select
                  value={chunkSizeMb}
                  onChange={(e) => setChunkSizeMb(Number(e.target.value))}
                  className="bg-dark-900 border border-slate-700 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none"
                >
                  <option value={4}>4 MB (Small)</option>
                  <option value={8}>8 MB (Medium)</option>
                  <option value={16}>16 MB (Optimal Default)</option>
                  <option value={32}>32 MB (Large)</option>
                  <option value={64}>64 MB (Ultra-Large)</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-800 bg-dark-950">
          <button
            onClick={handleClose}
            className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleStartDownload}
            disabled={!analysis || starting || selectedInterfaces.length === 0}
            className="flex items-center gap-2 px-5 py-2 rounded-xl bg-gradient-to-r from-blue-600 via-cyan-600 to-emerald-600 hover:from-blue-500 hover:to-emerald-500 text-white font-semibold text-xs shadow-lg shadow-blue-500/25 transition-all active:scale-95 disabled:opacity-40"
          >
            {starting ? 'Starting Download...' : 'Start Download'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
