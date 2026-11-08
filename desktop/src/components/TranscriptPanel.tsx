import React from 'react';
import { VoiceState } from '../types';
import { Bot, User } from 'lucide-react';

interface TranscriptPanelProps {
  transcript: string;
  response: string;
  voiceState: VoiceState;
}

export const TranscriptPanel: React.FC<TranscriptPanelProps> = ({
  transcript,
  response,
  voiceState,
}) => {
  if (!transcript && !response && voiceState === 'IDLE') {
    return (
      <div className="w-full max-w-2xl mx-auto p-4 bg-slate-900/40 border border-slate-800/80 rounded-2xl text-center text-xs text-slate-500 font-mono">
        Say <span className="text-cyan-400 font-bold">"Mike"</span> or press <span className="text-cyan-400 font-bold">Ctrl+Space</span> to give a command
      </div>
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto space-y-3 font-sans">
      {/* User Transcript */}
      {transcript && (
        <div className="flex items-start gap-3 p-3.5 bg-slate-900/70 border border-cyan-500/20 rounded-2xl text-xs text-slate-200 backdrop-blur-sm shadow-md animate-fade-in">
          <div className="p-1.5 bg-cyan-500/20 text-cyan-400 rounded-lg shrink-0">
            <User size={15} />
          </div>
          <div className="flex-1">
            <div className="text-[10px] text-cyan-400 font-mono font-bold tracking-wider mb-0.5">CHARAN</div>
            <p className="leading-relaxed">{transcript}</p>
          </div>
        </div>
      )}

      {/* Assistant Stream Response */}
      {(response || voiceState === 'THINKING') && (
        <div className="flex items-start gap-3 p-3.5 bg-slate-900/80 border border-cyan-400/30 rounded-2xl text-xs text-cyan-100 backdrop-blur-md shadow-lg shadow-cyan-950/40 animate-fade-in">
          <div className="p-1.5 bg-cyan-400/20 text-cyan-300 rounded-lg shrink-0">
            <Bot size={15} />
          </div>
          <div className="flex-1">
            <div className="text-[10px] text-cyan-300 font-mono font-bold tracking-wider mb-0.5">MIKE ASSISTANT</div>
            {voiceState === 'THINKING' && !response ? (
              <span className="text-slate-400 animate-pulse font-mono text-[11px]">Processing plan...</span>
            ) : (
              <p className="leading-relaxed whitespace-pre-wrap">{response}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
