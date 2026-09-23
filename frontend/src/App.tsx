import React, { useState, useEffect, useCallback } from 'react';
import type { 
  Download as DownloadType, 
  NetworkInfoResponse, 
  SpeedPoint
} from './types';
import { api, connectWebSocket, formatSpeed } from './services/api';
import { Header } from './components/Header';
import { SpeedChart } from './components/SpeedChart';
import { DownloadCard } from './components/DownloadCard';
import { NetworkMonitor } from './components/NetworkMonitor';
import { NewDownloadModal } from './components/NewDownloadModal';
import { DownloadDetailModal } from './components/DownloadDetailModal';
import { SettingsModal } from './components/SettingsModal';
import { 
  Activity, 
  Layers, 
  Network, 
  ArrowDownToLine, 
  Zap, 
  CheckCircle2, 
  Plus
} from 'lucide-react';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState('dashboard');
  const [downloads, setDownloads] = useState<DownloadType[]>([]);
  const [networkInfo, setNetworkInfo] = useState<NetworkInfoResponse>({
    mode: 'MULTI_CONNECTION',
    mode_description: 'Loading network topology...',
    simulation_mode: false,
    combined_speed_bps: 0,
    interfaces: []
  });
  const [speedHistory, setSpeedHistory] = useState<SpeedPoint[]>([]);
  const [selectedDownload, setSelectedDownload] = useState<DownloadType | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isNewDownloadOpen, setIsNewDownloadOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [defaultDir, setDefaultDir] = useState('');

  // Fetch initial state
  const loadData = useCallback(async () => {
    try {
      const [dls, net, cfg] = await Promise.all([
        api.getDownloads(),
        api.getNetworkInfo(),
        api.getSettings()
      ]);
      setDownloads(dls);
      setNetworkInfo(net);
      setDefaultDir(cfg.downloads_dir);
    } catch (err) {
      console.error('Failed to load initial MultiLink state:', err);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 3000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Continuous telemetry sync (1s interval) guaranteeing live graph updates
  useEffect(() => {
    const fetchTelemetry = async () => {
      try {
        const data = await api.getTelemetry();
        if (data.history && data.history.length > 0) {
          const points: SpeedPoint[] = data.history.map((pt) => {
            const timeLabel = new Date(pt.timestamp * 1000).toLocaleTimeString([], {
              minute: '2-digit',
              second: '2-digit'
            });
            const p: SpeedPoint = {
              timestamp: pt.timestamp,
              timeLabel,
              combined_mbps: pt.combined_bps / 1_000_000.0
            };
            Object.entries(pt.interfaces || {}).forEach(([ifId, bps]) => {
              p[ifId] = (bps as number) / 1_000_000.0;
            });
            return p;
          });
          setSpeedHistory(points);
          setNetworkInfo((prev) => ({
            ...prev,
            combined_speed_bps: data.combined_bps
          }));
        }
      } catch (err) {
        // silent fallback
      }
    };

    fetchTelemetry();
    const timer = setInterval(fetchTelemetry, 1000);
    return () => clearInterval(timer);
  }, []);

  // WebSocket for real-time live telemetry and event streaming
  useEffect(() => {
    const disconnect = connectWebSocket((event) => {
      if (event.type === 'speed_update') {
        const { timestamp, combined_bps, interfaces } = event.data;
        const timeLabel = new Date(timestamp * 1000).toLocaleTimeString([], {
          minute: '2-digit',
          second: '2-digit'
        });

        const point: SpeedPoint = {
          timestamp,
          timeLabel,
          combined_mbps: combined_bps / 1_000_000.0
        };

        // Add interface speeds to the point
        Object.entries(interfaces).forEach(([ifId, bps]: [string, any]) => {
          point[ifId] = bps / 1_000_000.0;
        });

        setSpeedHistory((prev) => {
          const next = [...prev, point];
          return next.slice(-45); // Keep last 45 data points (~45 seconds)
        });

        setNetworkInfo((prev) => ({
          ...prev,
          combined_speed_bps: combined_bps
        }));
      } else if (
        event.type === 'download_started' ||
        event.type === 'download_completed' ||
        event.type === 'download_paused' ||
        event.type === 'download_failed' ||
        event.type === 'download_created'
      ) {
        // Refresh downloads list immediately
        api.getDownloads().then(setDownloads).catch(console.error);
      }
    });

    return () => disconnect();
  }, []);

  // Action handlers
  const handlePause = async (id: string) => {
    await api.pauseDownload(id);
    loadData();
  };

  const handleResume = async (id: string) => {
    await api.resumeDownload(id);
    loadData();
  };

  const handleCancel = async (id: string) => {
    await api.cancelDownload(id);
    loadData();
  };

  const handleDelete = async (id: string) => {
    await api.deleteDownload(id, false);
    loadData();
  };

  const handleOpenDetails = (dl: DownloadType) => {
    setSelectedDownload(dl);
    setIsDetailOpen(true);
  };

  const activeDownloads = downloads.filter(
    (d) => d.status === 'DOWNLOADING' || d.status === 'INITIALIZING' || d.status === 'QUEUED'
  );
  const completedDownloads = downloads.filter((d) => d.status === 'COMPLETED');
  const usableNetworks = networkInfo.interfaces.filter((i) => i.usable && i.is_enabled);

  return (
    <div className="min-h-screen bg-dark-950 text-slate-100 flex flex-col selection:bg-brand-blue selection:text-white">
      {/* Header */}
      <Header
        currentTab={currentTab}
        onTabChange={setCurrentTab}
        onOpenNewDownload={() => setIsNewDownloadOpen(true)}
        onOpenSettings={() => setIsSettingsOpen(true)}
        mode={networkInfo.mode}
        modeDescription={networkInfo.mode_description}
        combinedSpeedBps={networkInfo.combined_speed_bps}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* DASHBOARD TAB */}
        {currentTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Top Stat Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Stat 1: Active Downloads */}
              <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-400">Active Downloads</p>
                  <p className="text-2xl font-extrabold text-white mt-1">
                    {activeDownloads.length}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {downloads.length} total queued/saved
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-blue-500/10 text-brand-cyan border border-blue-500/20">
                  <Layers className="w-5 h-5" />
                </div>
              </div>

              {/* Stat 2: Combined Speed */}
              <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-400">Combined Speed</p>
                  <p className="text-2xl font-extrabold text-brand-cyan font-mono mt-1">
                    {formatSpeed(networkInfo.combined_speed_bps)}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Aggregated Throughput</p>
                </div>
                <div className="p-3 rounded-xl bg-cyan-500/10 text-brand-cyan border border-cyan-500/20">
                  <Zap className="w-5 h-5" />
                </div>
              </div>

              {/* Stat 3: Available Networks */}
              <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-400">Available Networks</p>
                  <p className="text-2xl font-extrabold text-emerald-400 mt-1">
                    {usableNetworks.length}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    {networkInfo.interfaces.length} Total Adapters
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Network className="w-5 h-5" />
                </div>
              </div>

              {/* Stat 4: Completed Downloads */}
              <div className="glass-panel rounded-2xl p-5 border border-slate-800 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-400">Completed Files</p>
                  <p className="text-2xl font-extrabold text-white mt-1">
                    {completedDownloads.length}
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Checksum Verified</p>
                </div>
                <div className="p-3 rounded-xl bg-violet-500/10 text-violet-400 border border-violet-500/20">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Live Throughput Chart Card */}
            <div className="glass-panel rounded-2xl p-5 border border-slate-800">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Activity className="w-5 h-5 text-brand-cyan" />
                  <h3 className="text-sm font-bold text-white tracking-wide">
                    Live Real-Time Throughput
                  </h3>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                  <span className="w-2 h-2 rounded-full bg-brand-cyan animate-ping" />
                  <span>30s Rolling Stream</span>
                </div>
              </div>
              <SpeedChart data={speedHistory} interfaces={usableNetworks} />
            </div>

            {/* Active Downloads Section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white tracking-wide flex items-center gap-2">
                  <Layers className="w-4 h-4 text-brand-cyan" />
                  Active Downloads ({activeDownloads.length})
                </h3>
                {activeDownloads.length === 0 && (
                  <button
                    onClick={() => setIsNewDownloadOpen(true)}
                    className="text-xs text-brand-cyan hover:underline flex items-center gap-1"
                  >
                    <Plus className="w-3.5 h-3.5" /> Start New Download
                  </button>
                )}
              </div>

              {activeDownloads.length > 0 ? (
                <div className="space-y-3">
                  {activeDownloads.map((dl) => (
                    <DownloadCard
                      key={dl.id}
                      download={dl}
                      onPause={handlePause}
                      onResume={handleResume}
                      onCancel={handleCancel}
                      onDelete={handleDelete}
                      onOpenDetails={handleOpenDetails}
                    />
                  ))}
                </div>
              ) : (
                <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center space-y-3">
                  <div className="w-12 h-12 rounded-2xl bg-blue-500/10 text-brand-cyan border border-blue-500/20 flex items-center justify-center mx-auto">
                    <ArrowDownToLine className="w-6 h-6" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white">No Active Downloads</h4>
                    <p className="text-xs text-slate-400 max-w-sm mx-auto mt-1">
                      Ready to download faster by aggregating available network interfaces.
                    </p>
                  </div>
                  <button
                    onClick={() => setIsNewDownloadOpen(true)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-lg shadow-blue-500/20 transition-all"
                  >
                    <Plus className="w-4 h-4" />
                    Enter Download URL
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* DOWNLOADS TAB */}
        {currentTab === 'downloads' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-base font-bold text-white">All Downloads ({downloads.length})</h2>
              <button
                onClick={() => setIsNewDownloadOpen(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                New Download
              </button>
            </div>

            {downloads.length > 0 ? (
              <div className="space-y-3">
                {downloads.map((dl) => (
                  <DownloadCard
                    key={dl.id}
                    download={dl}
                    onPause={handlePause}
                    onResume={handleResume}
                    onCancel={handleCancel}
                    onDelete={handleDelete}
                    onOpenDetails={handleOpenDetails}
                  />
                ))}
              </div>
            ) : (
              <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
                No downloads found. Click "New Download" to get started.
              </div>
            )}
          </div>
        )}

        {/* NETWORKS TAB */}
        {currentTab === 'networks' && (
          <NetworkMonitor
            interfaces={networkInfo.interfaces}
            simulationMode={networkInfo.simulation_mode}
            mode={networkInfo.mode}
            modeDescription={networkInfo.mode_description}
            onRefresh={loadData}
          />
        )}

        {/* HISTORY TAB */}
        {currentTab === 'history' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-base font-bold text-white">
                Completed Downloads ({completedDownloads.length})
              </h2>
            </div>

            {completedDownloads.length > 0 ? (
              <div className="space-y-3">
                {completedDownloads.map((dl) => (
                  <DownloadCard
                    key={dl.id}
                    download={dl}
                    onPause={handlePause}
                    onResume={handleResume}
                    onCancel={handleCancel}
                    onDelete={handleDelete}
                    onOpenDetails={handleOpenDetails}
                  />
                ))}
              </div>
            ) : (
              <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
                No completed downloads yet.
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      {isNewDownloadOpen && (
        <NewDownloadModal
          isOpen={isNewDownloadOpen}
          onClose={() => setIsNewDownloadOpen(false)}
          onDownloadStarted={loadData}
          defaultDownloadsDir={defaultDir}
        />
      )}

      <DownloadDetailModal
        download={downloads.find(d => d.id === selectedDownload?.id) || selectedDownload}
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false);
          setSelectedDownload(null);
        }}
        onDownloadUpdated={loadData}
      />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        onSettingsSaved={loadData}
      />
    </div>
  );
};

export default App;
