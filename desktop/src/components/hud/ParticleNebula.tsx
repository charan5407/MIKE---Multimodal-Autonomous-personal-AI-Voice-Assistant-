import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { VoiceState } from '../../types';

interface ParticleNebulaProps {
  voiceState: VoiceState;
  lowPowerMode?: boolean;
}

export const ParticleNebula: React.FC<ParticleNebulaProps> = ({ voiceState, lowPowerMode = false }) => {
  const pointsRef = useRef<THREE.Points>(null);
  const count = lowPowerMode ? 120 : 360;

  // Generate randomized 3D particle positions
  const [positions, scales] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const scl = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      // Spherical distribution
      const r = 1.6 + Math.random() * 2.2;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      pos[i * 3 + 2] = r * Math.cos(phi);

      scl[i] = Math.random() * 0.04 + 0.015;
    }

    return [pos, scl];
  }, [count]);

  const pColor = useMemo(() => {
    switch (voiceState) {
      case 'LISTENING':
        return new THREE.Color('#00f0ff');
      case 'THINKING':
        return new THREE.Color('#c084fc');
      case 'SPEAKING':
        return new THREE.Color('#38bdf8');
      case 'STOPPED':
      case 'ERROR':
        return new THREE.Color('#ef4444');
      case 'IDLE':
      default:
        return new THREE.Color('#00e5ff');
    }
  }, [voiceState]);

  useFrame((_, delta) => {
    if (!pointsRef.current || lowPowerMode) return;
    pointsRef.current.rotation.y += delta * 0.08;
    pointsRef.current.rotation.x += delta * 0.04;
  });

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={positions.length / 3}
          array={positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="attributes-scale"
          count={scales.length}
          array={scales}
          itemSize={1}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.035}
        color={pColor}
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
};

