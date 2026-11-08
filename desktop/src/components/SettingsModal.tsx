import React, { useEffect, useState } from 'react';
import { AppSettings, AudioDevice } from '../types';
import { Settings as SettingsIcon, Mic, Sliders, Cpu, Shield, X } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  settings: AppSettings;
  onSave: (newSettings: Partial<AppSettings>) => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({
  isOpen,
  onClose,
  settings,
  onSave,
}) => {
  const [localSettings, setLocalSettings] = useState<AppSettings>(settings);
  const [devices, setDevices] = useState<AudioDevice[]>([]);

  useEffect(() => {
    setLocalSettings(settings);
  }, [settings]);

  useEffect(() => {
    if (isOpen) {
      fetch('http://127.0.0.1:8765/api/audio/devices')
        .then((res) => res.json())
        .then((data) => {
          if (data.devices) setDevices(data.devices);
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleToggle = (key: keyof AppSettings) => {
    const updated = { ...localSettings, [key]: !localSettings[key] };
    setLocalSettings(updated);
    onSave({ [key]: updated[key] });
  };

  const handleSelect = (key: keyof AppSettings, value: unknown) => {
    const updated = { ...localSettings, [key]: value };
    setLocalSettings(updated);
    onSave({ [key]: value });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fade-in">
      <div className="relative w-full max-w-2xl bg-slate-900/90 border border-cyan-500/30 rounded-2xl p-6 shadow-2xl shadow-cyan-950/50 text-slate-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-cyan-500/20 pb-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-cyan-500/10 rounded-lg text-cyan-400 border border-cyan-500/30">
              <SettingsIcon size={22} />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-wider text-cyan-400 font-mono">SYSTEM SETTINGS</h2>
              <p className="text-xs text-slate-400">Configure assistant voice, brain, privacy, and desktop behavior</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content List */}
        <div className="space-y-6 max-h-[60vh] overflow-y-auto pr-2">
          {/* 1. Wake Word Toggle */}
          <div className="flex items-center justify-between p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="flex items-center gap-3">
              <Mic className="text-cyan-400" size={20} />
              <div>
                <div className="text-sm font-semibold text-slate-100">Wake Word Detection</div>
                <div className="text-xs text-slate-400">Listen continuously for "Mike" / "Hey Mike"</div>
              </div>
            </div>
            <button
              onClick={() => handleToggle('wake_word_enabled')}
              className={`w-14 h-8 flex items-center rounded-full p-1 cursor-pointer transition ${
                localSettings.wake_word_enabled ? 'bg-cyan-500 justify-end' : 'bg-slate-700 justify-start'
              }`}
            >
              <div className="bg-slate-950 w-6 h-6 rounded-full shadow-md" />
            </button>
          </div>

          {/* 2. Microphone Selection */}
          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <label className="block text-sm font-semibold text-slate-100 mb-2">Microphone Input Device</label>
            <select
              value={localSettings.microphone_index}
              onChange={(e) => handleSelect('microphone_index', Number(e.target.value))}
              className="w-full bg-slate-900 border border-cyan-500/30 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-400"
            >
              <option value={-1}>Default System Microphone</option>
              {devices.map((d) => (
                <option key={d.index} value={d.index}>
                  [{d.index}] {d.name}
                </option>
              ))}
            </select>
          </div>

          {/* 3. Brain / Model Selection */}
          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="text-cyan-400" size={18} />
              <span className="text-sm font-semibold text-slate-100">Intelligence / LLM Provider</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'gemini', label: 'Gemini Free', desc: 'Google 2.0 Flash' },
                { id: 'groq', label: 'Groq Free', desc: 'Llama 3.3 70B' },
                { id: 'ollama', label: 'Ollama Local', desc: 'Offline Llama 3.1 8B' },
              ].map((p) => (
                <button
                  key={p.id}
                  onClick={() => handleSelect('primary_provider', p.id)}
                  className={`p-3 rounded-lg border text-left transition ${
                    localSettings.primary_provider === p.id
                      ? 'bg-cyan-500/20 border-cyan-400 text-cyan-200'
                      : 'bg-slate-900/60 border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <div className="text-xs font-bold">{p.label}</div>
                  <div className="text-[10px] text-slate-400">{p.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* 4. Voice Speed & Pitch */}
          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="flex items-center gap-2 mb-3">
              <Sliders className="text-cyan-400" size={18} />
              <span className="text-sm font-semibold text-slate-100">Voice Synthesis Cadence (Soft-Spoken)</span>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Calm / Relaxed (-4%)</span>
              <span className="text-cyan-400 font-mono">Neural Aria (Female)</span>
            </div>
          </div>

          {/* 5. Permission Security Tiers */}
          <div className="p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="text-cyan-400" size={18} />
              <span className="text-sm font-semibold text-slate-100">Action Permission Level</span>
            </div>
            <div className="text-xs text-slate-400 mb-3">
              Level C strictly requires voice or on-screen confirmation before sending WhatsApp messages or deleting files.
            </div>
            <div className="flex gap-2">
              {(['A', 'B', 'C'] as const).map((tier) => (
                <button
                  key={tier}
                  onClick={() => handleSelect('permission_tier', tier)}
                  className={`flex-1 py-2 rounded-lg border text-xs font-mono font-bold transition ${
                    localSettings.permission_tier === tier
                      ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300'
                      : 'bg-slate-900/60 border-slate-700 text-slate-400'
                  }`}
                >
                  Tier {tier} {tier === 'C' ? '(Strict)' : tier === 'B' ? '(Logged)' : '(Auto)'}
                </button>
              ))}
            </div>
          </div>

          {/* 6. Desktop Window Controls & Hotkeys */}
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center justify-between p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
              <span className="text-xs text-slate-300">Always on Top</span>
              <button
                onClick={() => {
                  const nextVal = !localSettings.always_on_top;
                  handleToggle('always_on_top');
                  if (window.mikeAPI) window.mikeAPI.toggleAlwaysOnTop(nextVal);
                }}
                className={`w-11 h-6 flex items-center rounded-full p-1 cursor-pointer transition ${
                  localSettings.always_on_top ? 'bg-cyan-500 justify-end' : 'bg-slate-700 justify-start'
                }`}
              >
                <div className="bg-slate-950 w-4 h-4 rounded-full shadow" />
              </button>
            </div>

            <div className="flex items-center justify-between p-4 bg-slate-800/40 rounded-xl border border-slate-700/50">
              <span className="text-xs text-slate-300">Start on Boot</span>
              <button
                onClick={() => {
                  const nextVal = !localSettings.start_on_boot;
                  handleToggle('start_on_boot');
                  if (window.mikeAPI) window.mikeAPI.setStartOnBoot(nextVal);
                }}
                className={`w-11 h-6 flex items-center rounded-full p-1 cursor-pointer transition ${
                  localSettings.start_on_boot ? 'bg-cyan-500 justify-end' : 'bg-slate-700 justify-start'
                }`}
              >
                <div className="bg-slate-950 w-4 h-4 rounded-full shadow" />
              </button>
            </div>
          </div>

          {/* Hotkey notice */}
          <div className="p-3 bg-cyan-950/30 border border-cyan-500/20 rounded-xl text-xs text-cyan-300 flex items-center justify-between font-mono">
            <span>EMERGENCY STOP HOTKEY</span>
            <span className="bg-slate-900 px-2 py-1 rounded border border-cyan-500/40">Ctrl + Alt + Shift + S</span>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded-xl text-xs tracking-wider transition font-mono"
          >
            APPLY & CLOSE
          </button>
        </div>
      </div>
    </div>
  );
};
