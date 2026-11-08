import React from 'react';
import { Activity, CheckCircle2, AlertCircle, XCircle, Clock } from 'lucide-react';

export interface ToolActivityItem {
  tool: string;
  tier: string;
  status: 'started' | 'success' | 'failed' | 'cancelled' | 'timeout';
  detail?: string;
  timestamp: number;
}

interface ToolActivityPanelProps {
  activities: ToolActivityItem[];
}

export const ToolActivityPanel: React.FC<ToolActivityPanelProps> = ({ activities }) => {
  if (activities.length === 0) return null;

  const getStatusIcon = (status: ToolActivityItem['status']) => {
    switch (status) {
      case 'started':
        return <Activity size={14} className="text-cyan-400 animate-spin" />;
      case 'success':
        return <CheckCircle2 size={14} className="text-emerald-400" />;
      case 'failed':
      case 'timeout':
        return <AlertCircle size={14} className="text-rose-400" />;
      case 'cancelled':
        return <XCircle size={14} className="text-amber-400" />;
    }
  };

  const getTierBadge = (tier: string) => {
    if (tier.includes('TIER_C')) {
      return <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/30">Tier C</span>;
    }
    if (tier.includes('TIER_B')) {
      return <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/30">Tier B</span>;
    }
    return <span className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">Tier A</span>;
  };

  return (
    <div className="w-full max-w-2xl mx-auto p-3 bg-slate-900/75 border border-cyan-500/20 rounded-2xl backdrop-blur-md shadow-lg shadow-cyan-950/30 space-y-2">
      <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 border-b border-slate-800 pb-1.5 px-1">
        <div className="flex items-center gap-1.5 text-cyan-400">
          <Clock size={13} />
          <span className="font-bold tracking-wider">TOOL ACTIVITY STREAM</span>
        </div>
        <span className="text-[10px] text-slate-500">{activities.length} recent action(s)</span>
      </div>

      <div className="space-y-1.5 max-h-32 overflow-y-auto pr-1">
        {activities.slice(-4).reverse().map((item, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between p-2 rounded-xl bg-slate-950/60 border border-slate-800/80 text-xs text-slate-200 animate-fade-in"
          >
            <div className="flex items-center gap-2">
              {getStatusIcon(item.status)}
              <span className="font-mono font-bold text-slate-100">{item.tool}</span>
              {getTierBadge(item.tier)}
            </div>

            <div className="text-[11px] text-slate-400 truncate max-w-[200px] font-mono">
              {item.detail || item.status}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
