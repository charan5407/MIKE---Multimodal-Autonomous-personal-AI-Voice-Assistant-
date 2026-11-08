import React, { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { HUDCanvas } from './components/hud/HUDCanvas';
import { VoiceSearchBar } from './components/VoiceSearchBar';
import { TranscriptPanel } from './components/TranscriptPanel';
import { SettingsModal } from './components/SettingsModal';
import { AppSettings } from './types';
import { Settings as SettingsIcon, Minus, X, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const { isConnected, voiceState, rms, transcript, response, sendAction } = useWebSocket();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lowPowerMode, setLowPowerMode] = useState(false);

  const [settings, setSettings] = useState<AppSettings>({
    wake_word_enabled: true,
    microphone_index: -1,
    voice_speed: '-4%',
    voice_pitch: '-2Hz',
    primary_provider: 'gemini',
    always_on_top: false,
    start_on_boot: false,
    permission_tier: 'C',
  });

  const handlePushToTalk = () => {
    sendAction('push_to_talk');
  };

  const handleStop = () => {
    sendAction('stop');
  };

  const handleQuery = (query: string) => {
    fetch('http://127.0.0.1:8765/api/action/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query }),
    }).catch((err) => console.error('Chat error:', err));
  };

  const handleSaveSettings = (updated: Partial<AppSettings>) => {
    setSettings((prev) => ({ ...prev, ...updated }));
    fetch('http://127.0.0.1:8765/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updated),
    }).catch((err) => console.error('Settings save error:', err));
  };

  const handleMinimize = () => {
    if (window.mikeAPI) {
      window.mikeAPI.minimizeToTray();
    }
  };

  const handleClose = () => {
    if (window.mikeAPI) {
      window.mikeAPI.closeWindow();
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950/95 text-slate-100 font-sans border border-cyan-500/30 rounded-2xl overflow-hidden shadow-2xl shadow-cyan-950/70 select-none">
      {/* Top Header / Frameless Drag Bar */}
      <header className="flex items-center justify-between px-5 py-3.5 bg-slate-900/60 border-b border-cyan-500/20 backdrop-blur-md">
        {/* Brand Element: The "C" Emblem */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-400 flex items-center justify-center font-mono font-bold text-cyan-400 text-sm shadow-md shadow-cyan-500/30">
            C
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-black text-sm tracking-widest text-cyan-400">MIKE</span>
              <span className="text-[10px] font-mono text-slate-400 border border-slate-700 px-1.5 py-0.2 rounded">v0.1.0</span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">Owner: Charan | AIML Desktop Agent</div>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-4 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900 border border-slate-800">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
            <span className="text-[11px] text-slate-300">{isConnected ? 'ONLINE' : 'CORE OFFLINE'}</span>
          </div>

          <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
            <ShieldCheck size={14} className="text-cyan-400" />
            <span>Tier {settings.permission_tier}</span>
          </div>
        </div>

        {/* Action & Window Controls */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setLowPowerMode((prev) => !prev)}
            title={lowPowerMode ? 'Low Power Mode: ON (Energy Saver)' : 'High Performance Mode (60 FPS)'}
            className={`px-2 py-1 rounded text-[10px] font-mono border transition ${
              lowPowerMode
                ? 'bg-amber-500/10 text-amber-400 border-amber-500/40'
                : 'bg-cyan-500/10 text-cyan-400 border-cyan-500/40'
            }`}
          >
            {lowPowerMode ? 'PWR-SAVER' : '60 FPS'}
          </button>

          <button
            onClick={() => setIsSettingsOpen(true)}
            title="Settings"
            className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/60 transition"
          >
            <SettingsIcon size={16} />
          </button>
          <button
            onClick={handleMinimize}
            title="Minimize to System Tray"
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800/60 transition"
          >
            <Minus size={16} />
          </button>
          <button
            onClick={handleClose}
            title="Hide Window"
            className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-slate-800/60 transition"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      {/* Main Interactive Stage */}
      <main className="flex-1 flex flex-col items-center justify-between p-6 overflow-y-auto">
        {/* Centerpiece 3D Orb Stage */}
        <div className="my-auto">
          <HUDCanvas voiceState={voiceState} rms={rms} lowPowerMode={lowPowerMode} />
        </div>

        {/* Bottom Interactive Area */}
        <div className="w-full space-y-4 mt-auto">
          {/* Live Transcript / Response Stream */}
          <TranscriptPanel transcript={transcript} response={response} voiceState={voiceState} />

          {/* Voice Search Bar */}
          <VoiceSearchBar
            voiceState={voiceState}
            onPushToTalk={handlePushToTalk}
            onStop={handleStop}
            onSubmitQuery={handleQuery}
          />
        </div>
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        settings={settings}
        onSave={handleSaveSettings}
      />
    </div>
  );
};
