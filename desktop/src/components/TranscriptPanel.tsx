import React, { useEffect, useRef } from 'react';
import { VoiceState, ChatMessageItem } from '../types';
import { Bot, User, Image as ImageIcon, Sparkles, Code2 } from 'lucide-react';

interface TranscriptPanelProps {
  messages: ChatMessageItem[];
  currentTranscript?: string;
  currentResponse?: string;
  voiceState: VoiceState;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  messages,
  currentTranscript,
  currentResponse,
  voiceState,
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages, live words, or stream tokens arrive
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, currentTranscript, currentResponse, voiceState]);

  const isEmpty =
    messages.length === 0 &&
    !currentTranscript &&
    !currentResponse &&
    voiceState === 'IDLE';

  if (isEmpty) {
    return (
      <div className="w-full max-w-2xl mx-auto p-3.5 bg-slate-900/40 border border-slate-800/80 rounded-2xl text-center text-xs text-slate-500 font-mono no-drag flex items-center justify-center gap-2">
        <Sparkles size={14} className="text-cyan-400" />
        <span>
          Say <span className="text-cyan-400 font-bold">"Mike"</span> or type below to start your query
        </span>
      </div>
    );
  }

  // Format code blocks, markdown images, or text nicely
  const renderMessageContent = (content: string) => {
    if (!content) return null;

    // 1. Check if message contains markdown image ![alt](url)
    if (content.includes('![') && content.includes('](')) {
      const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
      const parts = [];
      let lastIndex = 0;
      let match;
      while ((match = imgRegex.exec(content)) !== null) {
        if (match.index > lastIndex) {
          parts.push({ type: 'text', text: content.slice(lastIndex, match.index) });
        }
        let url = match[2];
        if (url.includes('generated_images')) {
          const fn = url.split(/[/\\]/).pop();
          if (fn) url = `http://127.0.0.1:8765/media/${fn}`;
        }
        parts.push({ type: 'image', alt: match[1] || 'Generated Visual', url });
        lastIndex = match.index + match[0].length;
      }
      if (lastIndex < content.length) {
        parts.push({ type: 'text', text: content.slice(lastIndex) });
      }

      return parts.map((item, idx) => {
        if (item.type === 'image') {
          return (
            <div key={idx} className="my-2.5 rounded-2xl overflow-hidden border border-cyan-500/40 bg-slate-950 shadow-xl shadow-cyan-950/60 max-w-sm group">
              <img
                src={item.url}
                alt={item.alt}
                className="w-full h-auto object-cover max-h-72 rounded-t-2xl hover:scale-[1.01] transition cursor-pointer"
                onClick={() => window.open(item.url, '_blank')}
                title="Click to view full image"
              />
              <div className="p-2 bg-slate-900/90 flex items-center justify-between text-[11px] font-mono text-cyan-300">
                <span className="truncate flex items-center gap-1.5">
                  <ImageIcon size={13} className="text-cyan-400 shrink-0" />
                  <span className="truncate">{item.alt}</span>
                </span>
                <span className="text-[9px] text-slate-500 shrink-0">Multimodal Artifact</span>
              </div>
            </div>
          );
        }
        return <p key={idx} className="leading-relaxed whitespace-pre-wrap select-text">{item.text}</p>;
      });
    }

    // 2. Check if message contains markdown code blocks
    if (content.includes('```')) {
      const parts = content.split(/(```[\s\S]*?```)/g);
      return parts.map((part, idx) => {
        if (part.startsWith('```')) {
          const lines = part.slice(3, -3).trim().split('\n');
          const lang = lines[0].match(/^[a-zA-Z0-9_-]+$/) ? lines[0] : '';
          const code = lang ? lines.slice(1).join('\n') : lines.join('\n');
          return (
            <div key={idx} className="my-2 rounded-xl bg-slate-950 border border-cyan-500/20 overflow-hidden font-mono text-[11px]">
              <div className="flex items-center justify-between px-3 py-1 bg-slate-900/80 border-b border-cyan-500/10 text-cyan-400 text-[10px]">
                <span className="flex items-center gap-1.5">
                  <Code2 size={12} />
                  <span>{lang.toUpperCase() || 'CODE'}</span>
                </span>
              </div>
              <pre className="p-3 overflow-x-auto text-slate-300 leading-normal selection:bg-cyan-500/30">
                <code>{code}</code>
              </pre>
            </div>
          );
        }
        return (
          <span key={idx} className="whitespace-pre-wrap select-text leading-relaxed">
            {part}
          </span>
        );
      });
    }

    return <p className="leading-relaxed whitespace-pre-wrap select-text">{content}</p>;
  };

  return (
    <div
      ref={scrollContainerRef}
      className="w-full max-w-2xl mx-auto max-h-[220px] md:max-h-[280px] overflow-y-auto space-y-2.5 font-sans pr-1.5 scrollbar-thin scrollbar-thumb-cyan-500/30 scrollbar-track-transparent no-drag"
    >
      {/* 1. All Historical Messages in this Active Conversation */}
      {messages.map((msg, index) => {
        const isUser = msg.role === 'user';
        return (
          <div
            key={msg.id || index}
            className={`flex items-start gap-3 p-3 rounded-2xl text-xs backdrop-blur-md shadow-md animate-fade-in ${
              isUser
                ? 'bg-slate-900/70 border border-cyan-500/20 text-slate-200'
                : 'bg-slate-900/85 border border-cyan-400/30 text-cyan-100 shadow-cyan-950/40'
            }`}
          >
            <div
              className={`p-1.5 rounded-lg shrink-0 ${
                isUser ? 'bg-cyan-500/20 text-cyan-400' : 'bg-cyan-400/20 text-cyan-300'
              }`}
            >
              {isUser ? <User size={15} /> : <Bot size={15} />}
            </div>

            <div className="flex-1 overflow-hidden">
              <div
                className={`text-[10px] font-mono font-bold tracking-wider mb-0.5 ${
                  isUser ? 'text-cyan-400' : 'text-cyan-300'
                }`}
              >
                {isUser ? 'CHARAN' : 'MIKE ASSISTANT'}
              </div>

              {renderMessageContent(msg.content)}

              {/* Render Media if attached (e.g. Generated Images) */}
              {msg.media_url && (
                <div className="mt-2.5 rounded-xl overflow-hidden border border-cyan-500/30 bg-slate-950 max-w-sm">
                  <img
                    src={msg.media_url}
                    alt="Generated multimodal artifact"
                    className="w-full h-auto object-cover max-h-60"
                  />
                  <div className="px-2.5 py-1 text-[10px] font-mono text-cyan-400 flex items-center gap-1.5 bg-slate-900/90">
                    <ImageIcon size={12} />
                    <span>Multimodal Generated Artifact</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* 2. Active User Spoken Query (if not yet finalized in messages) */}
      {voiceState !== 'IDLE' && currentTranscript && (
        <div className="flex items-start gap-3 p-3 bg-slate-900/70 border border-cyan-500/30 rounded-2xl text-xs text-slate-200 backdrop-blur-sm shadow-md animate-fade-in">
          <div className="p-1.5 bg-cyan-500/20 text-cyan-400 rounded-lg shrink-0">
            <User size={15} />
          </div>
          <div className="flex-1">
            <div className="text-[10px] text-cyan-400 font-mono font-bold tracking-wider mb-0.5">CHARAN</div>
            <p className="leading-relaxed select-text">{currentTranscript}</p>
          </div>
        </div>
      )}

      {/* 3. Active Assistant Streaming Response / Thinking Indicator */}
      {voiceState !== 'IDLE' && (currentResponse || voiceState === 'THINKING') && (
        <div className="flex items-start gap-3 p-3 bg-slate-900/85 border border-cyan-400/40 rounded-2xl text-xs text-cyan-100 backdrop-blur-md shadow-lg shadow-cyan-950/50 animate-fade-in">
          <div className="p-1.5 bg-cyan-400/20 text-cyan-300 rounded-lg shrink-0">
            <Bot size={15} />
          </div>
          <div className="flex-1">
            <div className="text-[10px] text-cyan-300 font-mono font-bold tracking-wider mb-0.5">MIKE ASSISTANT</div>
            {voiceState === 'THINKING' && !currentResponse ? (
              <span className="text-cyan-400/80 animate-pulse font-mono text-[11px] flex items-center gap-1.5">
                <Sparkles size={12} className="animate-spin" />
                <span>Thinking & formulating solution...</span>
              </span>
            ) : (
              renderMessageContent(currentResponse || '')
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
