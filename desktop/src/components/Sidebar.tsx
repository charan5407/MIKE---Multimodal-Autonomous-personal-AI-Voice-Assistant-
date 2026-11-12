import React, { useState, useEffect } from 'react';
import {
  Plus,
  MessageSquare,
  FolderGit2,
  Image as ImageIcon,
  Trash2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Code2,
  Sparkles,
  RefreshCw,
} from 'lucide-react';

export interface ChatSessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_active: boolean;
}

export interface ProjectItem {
  name: string;
  path: string;
  size: number;
  updated_at: string;
  extension: string;
}

export interface ImageItem {
  name: string;
  path: string;
  size: number;
  updated_at: string;
}

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  onSelectSession: (sessionId: string) => void;
  activeSessionId?: string | null;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  onNewChat,
  onSelectSession,
  activeSessionId,
}) => {
  const [activeTab, setActiveTab] = useState<'chats' | 'projects' | 'images'>('chats');
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchHistory = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/history');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (err) {
      console.debug('Could not fetch chat history:', err);
    }
  };

  const fetchProjects = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/projects');
      if (res.ok) {
        const data = await res.json();
        setProjects(data.projects || []);
      }
    } catch (err) {
      console.debug('Could not fetch projects:', err);
    }
  };

  const fetchImages = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8765/api/images');
      if (res.ok) {
        const data = await res.json();
        setImages(data.images || []);
      }
    } catch (err) {
      console.debug('Could not fetch images:', err);
    }
  };

  const refreshCurrentTab = () => {
    setIsLoading(true);
    if (activeTab === 'chats') fetchHistory();
    else if (activeTab === 'projects') fetchProjects();
    else if (activeTab === 'images') fetchImages();
    setTimeout(() => setIsLoading(false), 300);
  };

  useEffect(() => {
    fetchHistory();
    fetchProjects();
    fetchImages();
    const interval = setInterval(() => {
      if (activeTab === 'chats') fetchHistory();
    }, 5000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const handleDeleteSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await fetch(`http://127.0.0.1:8765/api/history/${id}`, { method: 'DELETE' });
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        onNewChat();
      }
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  };

  const handleOpenInVSCode = async (path: string) => {
    try {
      await fetch('http://127.0.0.1:8765/api/projects/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      });
    } catch (err) {
      console.error('Failed to open in VS Code:', err);
    }
  };

  if (!isOpen) {
    return (
      <div className="flex flex-col items-center py-3 px-1.5 bg-slate-900/80 border-r border-cyan-500/20 backdrop-blur-md w-12 transition-all duration-300 z-20">
        <button
          onClick={onToggle}
          title="Expand Sidebar"
          className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 transition mb-3"
        >
          <ChevronRight size={18} />
        </button>
        <button
          onClick={onNewChat}
          title="New Conversation"
          className="p-2 rounded-lg text-cyan-400 hover:bg-cyan-500/20 border border-cyan-500/30 transition mb-3"
        >
          <Plus size={18} />
        </button>
        <button
          onClick={() => {
            setActiveTab('chats');
            onToggle();
          }}
          title="Chat History"
          className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 transition mb-2"
        >
          <MessageSquare size={16} />
        </button>
        <button
          onClick={() => {
            setActiveTab('projects');
            onToggle();
          }}
          title="Code Projects"
          className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 transition mb-2"
        >
          <FolderGit2 size={16} />
        </button>
        <button
          onClick={() => {
            setActiveTab('images');
            onToggle();
          }}
          title="Images & Media"
          className="p-2 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-slate-800/80 transition"
        >
          <ImageIcon size={16} />
        </button>
      </div>
    );
  }

  return (
    <aside className="flex flex-col h-full bg-slate-900/90 border-r border-cyan-500/20 backdrop-blur-xl w-64 md:w-72 transition-all duration-300 select-none z-20">
      {/* Sidebar Header & New Chat Button */}
      <div className="p-3 border-b border-cyan-500/10 flex flex-col gap-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-cyan-400" />
            <span className="text-xs font-mono font-bold tracking-wider text-slate-200">MIKE WORKSPACE</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={refreshCurrentTab}
              title="Refresh"
              className={`p-1.5 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition ${
                isLoading ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw size={14} />
            </button>
            <button
              onClick={onToggle}
              title="Collapse Sidebar"
              className="p-1.5 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition"
            >
              <ChevronLeft size={16} />
            </button>
          </div>
        </div>

        {/* ChatGPT Style "New Chat" Action Button */}
        <button
          onClick={onNewChat}
          className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-xl bg-gradient-to-r from-cyan-950/60 to-slate-900 border border-cyan-500/40 hover:border-cyan-400 hover:bg-cyan-950/80 text-cyan-300 text-xs font-medium transition shadow-sm shadow-cyan-950"
        >
          <Plus size={16} className="text-cyan-400" />
          <span>New Conversation</span>
        </button>
      </div>

      {/* Navigation Tab Selector */}
      <div className="grid grid-cols-3 gap-1 p-2 bg-slate-950/50 border-b border-cyan-500/10 text-[11px] font-mono">
        <button
          onClick={() => setActiveTab('chats')}
          className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition ${
            activeTab === 'chats'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <MessageSquare size={13} />
          <span>Chats</span>
        </button>
        <button
          onClick={() => setActiveTab('projects')}
          className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition ${
            activeTab === 'projects'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <FolderGit2 size={13} />
          <span>Projects</span>
        </button>
        <button
          onClick={() => setActiveTab('images')}
          className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg transition ${
            activeTab === 'images'
              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
          }`}
        >
          <ImageIcon size={13} />
          <span>Media</span>
        </button>
      </div>

      {/* Scrollable Content Stage */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-2 flex flex-col gap-1.5">
        {/* Tab 1: Chat History */}
        {activeTab === 'chats' && (
          <>
            <div className="text-[10px] font-mono text-slate-500 px-2 py-1 uppercase tracking-wider">
              Previous Conversations
            </div>
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500 font-mono">
                No past conversations yet.
                <div className="text-[10px] text-slate-600 mt-1">Start speaking or typing to save chats.</div>
              </div>
            ) : (
              sessions.map((sess) => {
                const isActive = activeSessionId === sess.id || sess.is_active;
                return (
                  <div
                    key={sess.id}
                    onClick={() => onSelectSession(sess.id)}
                    className={`group flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer text-xs transition border ${
                      isActive
                        ? 'bg-cyan-950/40 border-cyan-500/40 text-cyan-200 shadow-sm shadow-cyan-950'
                        : 'border-transparent text-slate-300 hover:bg-slate-800/50 hover:text-white'
                    }`}
                  >
                    <div className="flex items-center gap-2 overflow-hidden">
                      <MessageSquare
                        size={14}
                        className={isActive ? 'text-cyan-400 shrink-0' : 'text-slate-500 shrink-0 group-hover:text-slate-300'}
                      />
                      <span className="truncate">{sess.title}</span>
                    </div>

                    <button
                      onClick={(e) => handleDeleteSession(e, sess.id)}
                      title="Delete chat"
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-rose-400 text-slate-500 transition rounded"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                );
              })
            )}
          </>
        )}

        {/* Tab 2: Projects (from ~/MikeProjects) */}
        {activeTab === 'projects' && (
          <>
            <div className="text-[10px] font-mono text-slate-500 px-2 py-1 uppercase tracking-wider flex items-center justify-between">
              <span>Code Projects</span>
              <span className="text-[9px] text-cyan-400 font-mono">~/MikeProjects</span>
            </div>
            {projects.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500 font-mono">
                No generated projects yet.
                <div className="text-[10px] text-slate-600 mt-1">Ask MIKE: "write a python program for bubble sort"</div>
              </div>
            ) : (
              projects.map((proj) => (
                <div
                  key={proj.path}
                  className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950/40 border border-cyan-500/10 hover:border-cyan-500/30 transition text-xs group"
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Code2 size={15} className="text-cyan-400 shrink-0" />
                    <div className="truncate">
                      <div className="text-slate-200 font-mono truncate">{proj.name}</div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        {(proj.size / 1024).toFixed(1)} KB • {proj.extension.toUpperCase()}
                      </div>
                    </div>
                  </div>

                  <button
                    onClick={() => handleOpenInVSCode(proj.path)}
                    title="Open in Visual Studio Code"
                    className="flex items-center gap-1 px-2 py-1 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-[10px] hover:bg-cyan-500/20 transition"
                  >
                    <span>VS Code</span>
                    <ExternalLink size={10} />
                  </button>
                </div>
              ))
            )}
          </>
        )}

        {/* Tab 3: Media & Generated Images */}
        {activeTab === 'images' && (
          <>
            <div className="text-[10px] font-mono text-slate-500 px-2 py-1 uppercase tracking-wider">
              Generated Media & Icons
            </div>
            {images.length === 0 ? (
              <div className="text-center py-8 text-xs text-slate-500 font-mono">
                No generated media found.
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 p-1">
                {images.map((img) => (
                  <div
                    key={img.path}
                    onClick={() => window.open(`http://127.0.0.1:8765/media/${img.name}`, '_blank')}
                    title={`Click to view ${img.name}`}
                    className="flex flex-col items-center p-2 rounded-xl bg-slate-950/40 border border-cyan-500/20 hover:border-cyan-400 hover:bg-slate-900/60 transition cursor-pointer group shadow-sm"
                  >
                    <div className="w-full h-20 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center overflow-hidden mb-1.5 relative">
                      <img
                        src={`http://127.0.0.1:8765/media/${img.name}`}
                        alt={img.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition"
                        onError={(e) => {
                          const target = e.target as HTMLElement;
                          target.style.display = 'none';
                        }}
                      />
                    </div>
                    <span className="text-[10px] font-mono text-cyan-300 truncate w-full text-center">
                      {img.name.replace('gen_', '').replace(/\.[^/.]+$/, '').replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Sidebar Footer */}
      <div className="p-2.5 border-t border-cyan-500/10 bg-slate-950/40 text-[11px] font-mono text-slate-500 flex items-center justify-between">
        <span className="text-cyan-400/80">MIKE Assistant</span>
        <span>Charan • AIML</span>
      </div>
    </aside>
  );
};
