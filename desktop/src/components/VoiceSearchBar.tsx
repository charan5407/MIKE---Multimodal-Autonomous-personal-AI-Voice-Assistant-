import React, { useState } from 'react';
import { Mic, Search, Square, Send } from 'lucide-react';
import { VoiceState } from '../types';

interface VoiceSearchBarProps {
  voiceState: VoiceState;
  onPushToTalk: () => void;
  onStop: () => void;
  onSubmitQuery: (query: string) => void;
}

export const VoiceSearchBar: React.FC<VoiceSearchBarProps> = ({
  voiceState,
  onPushToTalk,
  onStop,
  onSubmitQuery,
}) => {
  const [query, setQuery] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      onSubmitQuery(query.trim());
      setQuery('');
    }
  };

  const isListening = voiceState === 'LISTENING';
  const isBusy = voiceState === 'THINKING' || voiceState === 'SPEAKING';

  return (
    <div className="w-full max-w-2xl mx-auto">
      <form
        onSubmit={handleSubmit}
        className="relative flex items-center gap-2 bg-slate-900/80 border border-cyan-500/30 rounded-2xl p-2 shadow-lg shadow-cyan-950/30 backdrop-blur-md transition-all focus-within:border-cyan-400 focus-within:shadow-cyan-500/20"
      >
        {/* Search Icon */}
        <div className="pl-3 text-cyan-400/70">
          <Search size={18} />
        </div>

        {/* Input Field */}
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={
            isListening
              ? 'Listening to your voice...'
              : 'Ask MIKE anything, search web, or say "Mike"...'
          }
          className="flex-1 bg-transparent border-none text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans px-2"
        />

        {/* Push to Talk Button */}
        <button
          type="button"
          onClick={onPushToTalk}
          title="Push to Talk (Ctrl+Space)"
          className={`p-2.5 rounded-xl transition flex items-center justify-center ${
            isListening
              ? 'bg-rose-500 text-white animate-pulse shadow-lg shadow-rose-500/50'
              : 'bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
          }`}
        >
          <Mic size={18} />
        </button>

        {/* Submit Query Button (if typed) */}
        {query.trim() && (
          <button
            type="submit"
            className="p-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-xl transition font-bold"
          >
            <Send size={16} />
          </button>
        )}

        {/* Emergency Stop Button */}
        <button
          type="button"
          onClick={onStop}
          title="Emergency Stop (Ctrl+Alt+Shift+S)"
          className={`p-2.5 rounded-xl transition border ${
            isBusy || isListening
              ? 'bg-rose-600 hover:bg-rose-500 text-white border-rose-400/50 shadow-md shadow-rose-900/50'
              : 'bg-slate-800 text-slate-500 border-slate-700 hover:text-rose-400'
          }`}
        >
          <Square size={16} className={isBusy ? 'fill-white' : ''} />
        </button>
      </form>
    </div>
  );
};
