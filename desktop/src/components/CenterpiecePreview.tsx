import React from 'react';
import { VoiceState } from '../types';

interface CenterpiecePreviewProps {
  voiceState: VoiceState;
  rms: number;
}

export const CenterpiecePreview: React.FC<CenterpiecePreviewProps> = ({ voiceState, rms }) => {
  // Compute pulse multiplier from live microphone RMS
  const scale = 1.0 + Math.min(0.35, rms * 0.5);

  const getStateColors = () => {
    switch (voiceState) {
      case 'LISTENING':
        return {
          glow: 'rgba(0, 240, 255, 0.6)',
          border: 'border-cyan-400',
          ring1: 'animate-spin-slow border-cyan-400/60',
          ring2: 'animate-reverse-spin border-cyan-300/40',
          text: 'text-cyan-300',
        };
      case 'THINKING':
        return {
          glow: 'rgba(168, 85, 247, 0.6)',
          border: 'border-purple-400',
          ring1: 'animate-spin-fast border-purple-400/80',
          ring2: 'animate-reverse-spin border-cyan-400/60',
          text: 'text-purple-300',
        };
      case 'SPEAKING':
        return {
          glow: 'rgba(56, 189, 248, 0.7)',
          border: 'border-sky-400',
          ring1: 'animate-spin-normal border-sky-400/80',
          ring2: 'animate-reverse-spin border-cyan-400/50',
          text: 'text-sky-300',
        };
      case 'STOPPED':
        return {
          glow: 'rgba(239, 68, 68, 0.4)',
          border: 'border-rose-500',
          ring1: 'border-rose-500/40',
          ring2: 'border-rose-400/30',
          text: 'text-rose-400',
        };
      case 'ERROR':
        return {
          glow: 'rgba(239, 68, 68, 0.7)',
          border: 'border-rose-600',
          ring1: 'border-rose-600/70',
          ring2: 'border-rose-500/50',
          text: 'text-rose-400',
        };
      case 'IDLE':
      default:
        return {
          glow: 'rgba(0, 240, 255, 0.25)',
          border: 'border-cyan-500/40',
          ring1: 'animate-spin-very-slow border-cyan-500/30',
          ring2: 'animate-reverse-spin border-cyan-600/20',
          text: 'text-cyan-400',
        };
    }
  };

  const colors = getStateColors();

  return (
    <div className="relative flex items-center justify-center w-72 h-72 mx-auto select-none">
      {/* Outer Rotating Concentric Ring 1 */}
      <div
        className={`absolute inset-0 rounded-full border border-dashed ${colors.ring1} transition-all duration-300`}
        style={{
          boxShadow: `0 0 35px ${colors.glow}`,
          transform: `scale(${scale})`,
        }}
      />

      {/* Middle Counter-Rotating Ring 2 */}
      <div
        className={`absolute inset-4 rounded-full border-2 border-dotted ${colors.ring2} transition-all duration-300`}
      />

      {/* Inner Accent Ring 3 */}
      <div
        className={`absolute inset-8 rounded-full border border-cyan-500/30 transition-all duration-200`}
        style={{
          boxShadow: `inset 0 0 20px ${colors.glow}`,
        }}
      />

      {/* Glossy Metallic "C" (Charan) Core Emblem */}
      <div
        className="relative z-10 flex flex-col items-center justify-center w-36 h-36 rounded-full bg-slate-950/80 border-2 border-cyan-400/50 backdrop-blur-xl shadow-2xl transition-transform duration-100"
        style={{
          transform: `scale(${scale})`,
          boxShadow: `0 0 25px ${colors.glow}, inset 0 0 15px rgba(0,240,255,0.2)`,
        }}
      >
        <span
          className={`text-6xl font-black tracking-tighter font-mono ${colors.text} drop-shadow-[0_0_12px_rgba(0,240,255,0.8)]`}
        >
          C
        </span>
        <div className="text-[10px] tracking-widest text-cyan-400/70 font-mono mt-1 uppercase">
          {voiceState}
        </div>
      </div>
    </div>
  );
};
