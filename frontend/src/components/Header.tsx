import React from 'react';
import { 
  Activity, 
  Network, 
  Settings as SettingsIcon, 
  Plus, 
  History, 
  Layers
} from 'lucide-react';
import type { OperatingMode } from '../types';
import { formatSpeed } from '../services/api';

interface HeaderProps {
  currentTab: string;
  onTabChange: (tab: string) => void;
  onOpenNewDownload: () => void;
  onOpenSettings: () => void;
  mode: OperatingMode;
  modeDescription: string;
  combinedSpeedBps: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentTab,
  onTabChange,
  onOpenNewDownload,
  onOpenSettings,
  mode,
  modeDescription,
  combinedSpeedBps
}) => {
  const getModeBadge = () => {
    switch (mode) {
      case 'TRUE_MULTI_INTERFACE':
        return {
          label: 'Multi-Interface Active',
          bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
          dot: 'bg-emerald-400 animate-pulse'
        };
      case 'MULTI_CONNECTION':
        return {
          label: 'Multi-Connection Accelerated',
          bg: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
          dot: 'bg-blue-400'
        };
      case 'SIMULATION_MODE':
        return {
          label: 'Simulation Mode Active',
          bg: 'bg-violet-500/10 text-violet-400 border-violet-500/30',
          dot: 'bg-violet-400 animate-ping'
        };
      case 'SINGLE_CONNECTION':
      default:
        return {
          label: 'Single Connection',
          bg: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
          dot: 'bg-amber-400'
        };
    }
  };

  const badge = getModeBadge();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-dark-900/90 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3 cursor-pointer" onClick={() => onTabChange('dashboard')}>
              <div className="relative w-10 h-10 rounded-xl overflow-hidden shadow-lg shadow-cyan-500/20 ring-1 ring-cyan-500/30 shrink-0">
                <img src="/icon.png" alt="MultiLink Logo" className="w-full h-full object-cover" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-300 bg-clip-text text-transparent">
                    MultiLink
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                    PRO
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 font-medium">Multi-Network Aggregation Engine</p>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="hidden md:flex items-center gap-1 pl-4 border-l border-slate-800">
              <button
                onClick={() => onTabChange('dashboard')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  currentTab === 'dashboard'
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Activity className="w-4 h-4" />
                Dashboard
              </button>

              <button
                onClick={() => onTabChange('downloads')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  currentTab === 'downloads'
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Layers className="w-4 h-4" />
                Downloads
              </button>

              <button
                onClick={() => onTabChange('networks')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  currentTab === 'networks'
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <Network className="w-4 h-4" />
                Networks
              </button>

              <button
                onClick={() => onTabChange('history')}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  currentTab === 'history'
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                <History className="w-4 h-4" />
                History
              </button>
            </nav>
          </div>

          {/* Right Controls: Mode Badge, Speed Ticker, New Download, Settings */}
          <div className="flex items-center gap-3">
            {/* Mode badge */}
            <div 
              className={`hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full border text-xs font-medium transition-all cursor-help ${badge.bg}`}
              title={modeDescription}
            >
              <span className={`w-2 h-2 rounded-full ${badge.dot}`} />
              <span>{badge.label}</span>
            </div>

            {/* Combined Speed Meter */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-dark-850 border border-slate-800">
              <span className="text-[11px] text-slate-400 font-medium">TOTAL:</span>
              <span className="font-mono text-sm font-bold text-white tracking-wide">
                {formatSpeed(combinedSpeedBps)}
              </span>
            </div>

            {/* New Download Action */}
            <button
              onClick={onOpenNewDownload}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-medium text-xs shadow-lg shadow-blue-500/25 transition-all active:scale-95"
            >
              <Plus className="w-4 h-4" />
              <span>New Download</span>
            </button>

            {/* Settings button */}
            <button
              onClick={onOpenSettings}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 border border-transparent hover:border-slate-700 transition-all"
              title="Settings"
            >
              <SettingsIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
