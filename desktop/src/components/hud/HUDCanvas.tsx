import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { CenterpieceC } from './CenterpieceC';
import { ConcentricRings } from './ConcentricRings';
import { ParticleNebula } from './ParticleNebula';
import { VoiceState } from '../../types';

interface HUDCanvasProps {
  voiceState: VoiceState;
  rms: number;
  lowPowerMode?: boolean;
}

export const HUDCanvas: React.FC<HUDCanvasProps> = ({
  voiceState,
  rms,
  lowPowerMode = false,
}) => {
  return (
    <div className="relative w-80 h-80 sm:w-96 sm:h-96 mx-auto select-none pointer-events-none">
      <Canvas
        camera={{ position: [0, 0, 6.8], fov: 45 }}
        gl={{
          alpha: true,
          antialias: !lowPowerMode,
          powerPreference: 'high-performance',
        }}
        dpr={lowPowerMode ? 1 : [1, 2]}
        className="w-full h-full"
      >
        <ambientLight intensity={0.35} />
        
        {/* Key Lighting */}
        <pointLight position={[2, 3, 4]} intensity={2.2} color="#00f0ff" />
        <pointLight position={[-2, -3, -2]} intensity={1.5} color="#0055ff" />
        <pointLight position={[0, -2, 3]} intensity={1.0} color="#a855f7" />

        <Suspense fallback={null}>
          <group position={[0, 0, 0]}>
            {/* 3D Glossy Metallic Letter "C" */}
            <CenterpieceC voiceState={voiceState} rms={rms} lowPowerMode={lowPowerMode} />

            {/* Multiple 360-degree Concentric Rotating Rings */}
            <ConcentricRings voiceState={voiceState} rms={rms} />

            {/* Cybernetic Particle Cloud */}
            <ParticleNebula voiceState={voiceState} lowPowerMode={lowPowerMode} />
          </group>
        </Suspense>
      </Canvas>

      {/* State Badge Below Centerpiece */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex items-center gap-2 px-3 py-1 bg-slate-900/80 border border-cyan-500/30 rounded-full backdrop-blur-md text-[10px] font-mono tracking-widest text-cyan-400 shadow-lg shadow-cyan-950/60 uppercase">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            voiceState === 'LISTENING'
              ? 'bg-rose-500 animate-ping'
              : voiceState === 'THINKING'
              ? 'bg-purple-400 animate-pulse'
              : voiceState === 'SPEAKING'
              ? 'bg-sky-400 animate-pulse'
              : voiceState === 'STOPPED'
              ? 'bg-amber-400'
              : 'bg-cyan-400'
          }`}
        />
        <span>{voiceState}</span>
      </div>
    </div>
  );
};
