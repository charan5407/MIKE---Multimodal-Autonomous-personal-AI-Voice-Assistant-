import React, { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { HUDCanvas } from './components/hud/HUDCanvas';
import { VoiceSearchBar } from './components/VoiceSearchBar';
import { TranscriptPanel } from './components/TranscriptPanel';
import { ToolActivityPanel } from './components/ToolActivityPanel';
import { SettingsModal } from './components/SettingsModal';
import { Sidebar } from './components/Sidebar';
import { AppSettings, ChatMessageItem } from './types';
import {
  Settings as SettingsIcon,
  Minus,
  Maximize2,
  Minimize2,
  X,
  ShieldCheck,
  PanelLeft,
  PanelLeftClose,
} from 'lucide-react';

export const App: React.FC = () => {
  const { isConnected, voiceState, rms, transcript, response, toolActivities, sendAction } = useWebSocket();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [lowPowerMode, setLowPowerMode] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);

  // ChatGPT-style Sidebar and Continuous Conversation Thread
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);

  const [settings, setSettings] = useState<AppSettings>({
    wake_word_enabled: true,
    microphone_index: -1,
    voice_speed: '-4%',
    voice_pitch: '-2Hz',
    primary_provider: 'groq',
    always_on_top: false,
    start_on_boot: false,
    permission_tier: 'C',
  });

  // Load initial active session messages on startup
  useEffect(() => {
    fetch('http://127.0.0.1:8765/api/history')
      .then((res) => res.json())
      .then((data) => {
        const sessions = data.sessions || [];
        const active = sessions.find((s: any) => s.is_active) || sessions[0];
        if (active) {
          handleSelectSession(active.id);
        }
      })
      .catch((err) => console.debug('Initial history load error:', err));
  }, []);

  // When a turn completes and assistant finished speaking, commit the turn to the message history thread
  useEffect(() => {
    if (voiceState === 'IDLE' && response && transcript) {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === 'assistant' && last.content === response) {
          return prev;
        }
        return [
          ...prev,
          { id: `u_${Date.now()}`, role: 'user', content: transcript },
          { id: `a_${Date.now()}`, role: 'assistant', content: response },
        ];
      });
    }
  }, [voiceState, response, transcript]);

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

  const handleNewChat = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/history/new', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setActiveSessionId(data.session?.id || null);
        setMessages([]);
      }
    } catch (err) {
      console.error('New chat error:', err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      const res = await fetch(`http://127.0.0.1:8765/api/history/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        setActiveSessionId(sessionId);
        const msgs = (data.session?.messages || []).map((m: any, idx: number) => ({
          id: `msg_${idx}_${Date.now()}`,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          media_url: m.media_url,
        }));
        setMessages(msgs);
      }
    } catch (err) {
      console.error('Load session error:', err);
    }
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

  const handleToggleMaximize = async () => {
    if (window.mikeAPI?.toggleMaximize) {
      const isMax = await window.mikeAPI.toggleMaximize();
      setIsMaximized(!!isMax);
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
      <header
        onDoubleClick={handleToggleMaximize}
        className="drag-header flex items-center justify-between px-4 py-2.5 bg-slate-900/70 border-b border-cyan-500/20 backdrop-blur-md cursor-grab active:cursor-grabbing"
      >
        {/* Brand Element: The "C" Emblem & Sidebar Toggle */}
        <div className="flex items-center gap-2.5 no-drag">
          <button
            onClick={() => setIsSidebarOpen((prev) => !prev)}
            title={isSidebarOpen ? 'Collapse Sidebar' : 'Expand Sidebar (History, Projects, Media)'}
            className="p-1.5 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 transition"
          >
            {isSidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeft size={18} />}
          </button>

          <div className="w-8 h-8 rounded-full bg-cyan-500/10 border border-cyan-400 flex items-center justify-center font-mono font-bold text-cyan-400 text-sm shadow-md shadow-cyan-500/30">
            C
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-black text-sm tracking-widest text-cyan-400">MIKE</span>
              <span className="text-[10px] font-mono text-slate-400 border border-slate-700 px-1.5 py-0.2 rounded">v0.1.0</span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">Owner: Charan | AIML Multimodal Agent</div>
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex items-center gap-4 text-xs font-mono no-drag">
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
        <div className="flex items-center gap-1.5 no-drag">
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
            onClick={handleToggleMaximize}
            title={isMaximized ? 'Restore Window' : 'Maximize / Fullscreen'}
            className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/60 transition"
          >
            {isMaximized ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
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

      {/* Main Body Layout with ChatGPT Style Left Sidebar */}
      <div className="flex-1 flex flex-row overflow-hidden relative">
        <Sidebar
          isOpen={isSidebarOpen}
          onToggle={() => setIsSidebarOpen((prev) => !prev)}
          onNewChat={handleNewChat}
          onSelectSession={handleSelectSession}
          activeSessionId={activeSessionId}
        />

        {/* Main Interactive Stage */}
        <main className="no-drag flex-1 flex flex-col items-center justify-between p-4 md:p-6 overflow-hidden">
          {/* Centerpiece 3D Orb Stage */}
          <div className="flex-1 flex items-center justify-center min-h-[160px] max-h-[340px] w-full">
            <HUDCanvas voiceState={voiceState} rms={rms} lowPowerMode={lowPowerMode} />
          </div>

          {/* Bottom Interactive Area */}
          <div className="w-full max-w-2xl flex flex-col gap-2.5 mt-auto pt-2 z-10">
            {/* Tool Activity Stream Panel */}
            <ToolActivityPanel activities={toolActivities} />

            {/* Live Continuous Transcript / Response Stream Panel */}
            <TranscriptPanel
              messages={messages}
              currentTranscript={transcript}
              currentResponse={response}
              voiceState={voiceState}
            />

            {/* Voice Search Bar - always pinned */}
            <VoiceSearchBar
              voiceState={voiceState}
              onPushToTalk={handlePushToTalk}
              onStop={handleStop}
              onSubmitQuery={handleQuery}
            />
          </div>
        </main>
      </div>

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
