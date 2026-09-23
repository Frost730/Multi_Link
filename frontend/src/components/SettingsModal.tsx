import React, { useState, useEffect } from 'react';
import { 
  X, 
  Settings as SettingsIcon, 
  ShieldAlert, 
  CheckCircle2, 
  Save
} from 'lucide-react';
import type { Settings as SettingsType } from '../types';
import { api } from '../services/api';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSettingsSaved?: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  onSettingsSaved
}) => {
  const [settings, setSettings] = useState<SettingsType | null>(null);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      api.getSettings().then(setSettings).catch(console.error);
    }
  }, [isOpen]);

  if (!isOpen || !settings) return null;

  const handleSave = async () => {
    setSaving(true);
    setSuccess(false);
    try {
      await api.updateSettings(settings);
      setSuccess(true);
      if (onSettingsSaved) onSettingsSaved();
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 1000);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-lg rounded-2xl border border-slate-700/80 shadow-2xl overflow-hidden bg-dark-900">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-blue-500/10 text-brand-cyan border border-blue-500/20">
              <SettingsIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Application Settings</h3>
              <p className="text-xs text-slate-400">Download Engine & Security Preferences</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6 space-y-4 text-xs">
          {/* Download Directory */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1.5">
              Default Download Directory
            </label>
            <input
              type="text"
              value={settings.downloads_dir}
              onChange={(e) => setSettings({ ...settings, downloads_dir: e.target.value })}
              className="w-full bg-dark-950 border border-slate-800 focus:border-brand-blue rounded-xl px-3.5 py-2.5 text-slate-200 focus:outline-none font-mono"
            />
          </div>

          {/* Chunk Size & Concurrency */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-300 font-semibold mb-1.5">
                Default Chunk Size
              </label>
              <select
                value={settings.default_chunk_size_mb}
                onChange={(e) => setSettings({ ...settings, default_chunk_size_mb: Number(e.target.value) })}
                className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none"
              >
                <option value={4}>4 MB</option>
                <option value={8}>8 MB</option>
                <option value={16}>16 MB (Recommended)</option>
                <option value={32}>32 MB</option>
                <option value={64}>64 MB</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1.5">
                Max Parallel Connections
              </label>
              <input
                type="number"
                min={1}
                max={32}
                value={settings.max_concurrent_connections}
                onChange={(e) => setSettings({ ...settings, max_concurrent_connections: Number(e.target.value) })}
                className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none font-mono"
              />
            </div>
          </div>

          {/* Max Retries */}
          <div>
            <label className="block text-slate-300 font-semibold mb-1.5">
              Max Retries Per Chunk
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={settings.max_retries}
              onChange={(e) => setSettings({ ...settings, max_retries: Number(e.target.value) })}
              className="w-full bg-dark-950 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none font-mono"
            />
          </div>

          {/* Checkbox Toggles */}
          <div className="space-y-3 pt-2 border-t border-slate-800/80">
            <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-slate-800/80 cursor-pointer">
              <div>
                <div className="text-slate-200 font-semibold">Verify SHA-256 Checksum</div>
                <div className="text-[11px] text-slate-400">Stream-verifies integrity before finalizing file</div>
              </div>
              <input
                type="checkbox"
                checked={settings.verify_checksum}
                onChange={(e) => setSettings({ ...settings, verify_checksum: e.target.checked })}
                className="rounded text-brand-blue cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-slate-800/80 cursor-pointer">
              <div>
                <div className="text-slate-200 font-semibold">Enable Simulation Mode</div>
                <div className="text-[11px] text-slate-400">Emulates Ethernet, Wi-Fi, and USB links</div>
              </div>
              <input
                type="checkbox"
                checked={settings.simulation_mode_enabled}
                onChange={(e) => setSettings({ ...settings, simulation_mode_enabled: e.target.checked })}
                className="rounded text-violet-500 cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-xl bg-dark-950 border border-slate-800/80 cursor-pointer">
              <div>
                <div className="text-slate-200 font-semibold flex items-center gap-1.5">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
                  Allow Local / Private IP Downloads
                </div>
                <div className="text-[11px] text-slate-500">
                  Allows downloading from 127.0.0.1 or LAN (Disables SSRF protection)
                </div>
              </div>
              <input
                type="checkbox"
                checked={settings.allow_private_network_downloads}
                onChange={(e) => setSettings({ ...settings, allow_private_network_downloads: e.target.checked })}
                className="rounded text-amber-500 cursor-pointer"
              />
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-dark-950">
          <div>
            {success && (
              <span className="text-emerald-400 text-xs flex items-center gap-1 font-medium">
                <CheckCircle2 className="w-4 h-4" /> Settings saved!
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs shadow-lg shadow-blue-500/25 transition-all"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save Preferences'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
