import React, { useState } from 'react';
import type { 
  NetworkInterface, 
  OperatingMode, 
  BandwidthTestResult 
} from '../types';
import { 
  Wifi, 
  Network as NetworkIcon, 
  Smartphone, 
  ShieldCheck, 
  Layers, 
  RefreshCw,
  Gauge,
  Sliders,
  CheckCircle2,
  XCircle,
  Activity
} from 'lucide-react';
import { formatSpeed, api } from '../services/api';

interface NetworkMonitorProps {
  interfaces: NetworkInterface[];
  simulationMode: boolean;
  mode: OperatingMode;
  modeDescription: string;
  onRefresh: () => void;
}

export const NetworkMonitor: React.FC<NetworkMonitorProps> = ({
  interfaces,
  simulationMode,
  modeDescription,
  onRefresh
}) => {
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, BandwidthTestResult>>({});
  const [togglingSim, setTogglingSim] = useState(false);

  const getInterfaceIcon = (type: string) => {
    switch (type) {
      case 'ethernet':
        return <NetworkIcon className="w-5 h-5 text-emerald-400" />;
      case 'wifi':
        return <Wifi className="w-5 h-5 text-blue-400" />;
      case 'usb_tether':
        return <Smartphone className="w-5 h-5 text-amber-400" />;
      case 'vpn':
        return <ShieldCheck className="w-5 h-5 text-violet-400" />;
      default:
        return <Layers className="w-5 h-5 text-slate-400" />;
    }
  };

  const handleToggle = async (iface: NetworkInterface) => {
    try {
      await api.toggleInterface(iface.id, !iface.is_enabled);
      onRefresh();
    } catch (err) {
      console.error('Failed to toggle interface:', err);
    }
  };

  const handleTestBandwidth = async (iface: NetworkInterface) => {
    setTestingId(iface.id);
    try {
      const res = await api.testBandwidth(iface.id);
      setTestResults(prev => ({ ...prev, [iface.id]: res }));
    } catch (err: any) {
      setTestResults(prev => ({
        ...prev,
        [iface.id]: {
          interface_id: iface.id,
          interface_name: iface.name,
          speed_mbps: 0,
          latency_ms: 0,
          success: false,
          error: err.message || 'Test failed'
        }
      }));
    } finally {
      setTestingId(null);
    }
  };

  const handleToggleSimulation = async () => {
    setTogglingSim(true);
    try {
      await api.toggleSimulation(!simulationMode);
      onRefresh();
    } catch (err) {
      console.error('Failed to toggle simulation mode:', err);
    } finally {
      setTogglingSim(false);
    }
  };

  const activeInterfaces = interfaces.filter(
    (iface) => iface.is_simulated || (iface.status === 'connected' && iface.ipv4 && iface.usable && !iface.ipv4.startsWith('169.254.'))
  );

  return (
    <div className="space-y-6">
      {/* Top Banner: Mode & Simulation Switch */}
      <div className="glass-panel rounded-2xl p-5 border border-slate-800 bg-gradient-to-r from-dark-900 to-dark-850">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-brand-cyan" />
              <h2 className="text-base font-bold text-white tracking-wide">Active Network Connections</h2>
              <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
                {activeInterfaces.length} Active
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-2xl leading-relaxed">
              {modeDescription}
            </p>
          </div>

          {/* Simulation Mode Toggle Button */}
          <div className="flex items-center gap-3 bg-dark-950/80 p-2.5 rounded-xl border border-slate-800 self-start md:self-auto">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-violet-400" />
              <div>
                <div className="text-xs font-semibold text-white">Simulation Mode</div>
                <div className="text-[10px] text-slate-400">Emulate Ethernet + Wi-Fi + USB</div>
              </div>
            </div>
            <button
              onClick={handleToggleSimulation}
              disabled={togglingSim}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${
                simulationMode ? 'bg-violet-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  simulationMode ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Interface Cards Grid */}
      {activeInterfaces.length === 0 ? (
        <div className="glass-panel rounded-2xl p-8 border border-slate-800 text-center text-slate-400 text-xs">
          No active network connections detected. Ensure your Ethernet or Wi-Fi adapter is plugged in and connected.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {activeInterfaces.map((iface) => {
          const testRes = testResults[iface.id];
          const isTesting = testingId === iface.id;

          return (
            <div
              key={iface.id}
              className={`glass-panel rounded-2xl p-5 border transition-all ${
                iface.is_enabled && iface.usable
                  ? 'border-slate-800 hover:border-slate-700'
                  : 'border-slate-850 opacity-60'
              }`}
            >
              {/* Card Header */}
              <div className="flex items-start justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/60">
                    {getInterfaceIcon(iface.type)}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white flex items-center gap-2">
                      {iface.name}
                      {iface.is_simulated && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 border border-violet-500/30 uppercase font-mono">
                          SIM
                        </span>
                      )}
                    </h3>
                    <p className="text-[11px] text-slate-400 truncate max-w-[180px]">
                      {iface.description || iface.type.toUpperCase()}
                    </p>
                  </div>
                </div>

                {/* Enable / Disable toggle */}
                <button
                  onClick={() => handleToggle(iface)}
                  title={iface.is_enabled ? "Click to disable this adapter" : "Click to enable this adapter"}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 ${
                    iface.is_enabled
                      ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25'
                      : 'bg-slate-800 text-slate-400 border border-slate-700 hover:text-slate-200 hover:border-slate-600'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full ${iface.is_enabled ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                  {iface.is_enabled ? 'Active' : 'Disabled'}
                </button>
              </div>

              {/* Network Details */}
              <div className="space-y-2 py-2 border-y border-slate-800/60 text-xs">
                <div className="flex justify-between items-center text-slate-400">
                  <span>IPv4 Address:</span>
                  <span className="font-mono text-slate-200">{iface.ipv4 || 'None'}</span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Link Speed:</span>
                  <span className="font-mono text-slate-200">
                    {iface.speed_mbps > 0 ? `${iface.speed_mbps} Mbps` : 'Dynamic'}
                  </span>
                </div>
                <div className="flex justify-between items-center text-slate-400">
                  <span>Connection:</span>
                  <span className={`flex items-center gap-1 font-medium ${
                    iface.status === 'connected' ? 'text-emerald-400' : 'text-slate-500'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      iface.status === 'connected' ? 'bg-emerald-400' : 'bg-slate-600'
                    }`} />
                    {iface.status}
                  </span>
                </div>
              </div>

              {/* Real-time Throughput Gauge */}
              <div className="mt-4 pt-1">
                <div className="flex justify-between items-center text-xs mb-1.5">
                  <span className="text-slate-400 flex items-center gap-1">
                    <Gauge className="w-3.5 h-3.5 text-brand-cyan" />
                    Live Speed
                  </span>
                  <span className="font-mono font-bold text-brand-cyan text-sm">
                    {formatSpeed(iface.current_speed_bps)}
                  </span>
                </div>
                {/* Visual throughput bar */}
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-brand-blue to-brand-cyan transition-all duration-300"
                    style={{
                      width: `${Math.min(100, (iface.current_speed_bps / (50 * 1000 * 1000)) * 100)}%`
                    }}
                  />
                </div>
              </div>

              {/* Bandwidth Test Result & Action */}
              <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between">
                {testRes ? (
                  <div className="text-[11px] font-mono flex items-center gap-2">
                    {testRes.success ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {testRes.latency_ms}ms · {testRes.speed_mbps} Mbps
                      </span>
                    ) : (
                      <span className="text-rose-400 flex items-center gap-1" title={testRes.error}>
                        <XCircle className="w-3.5 h-3.5" />
                        Unreachable
                      </span>
                    )}
                  </div>
                ) : (
                  <span className="text-[11px] text-slate-500">No test yet</span>
                )}

                <button
                  onClick={() => handleTestBandwidth(iface)}
                  disabled={isTesting || !iface.is_enabled}
                  className="flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-700/80 text-slate-300 border border-slate-700 transition-all disabled:opacity-40"
                >
                  <RefreshCw className={`w-3 h-3 ${isTesting ? 'animate-spin text-brand-cyan' : ''}`} />
                  {isTesting ? 'Testing...' : 'Test Speed'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
      )}
    </div>
  );
};
