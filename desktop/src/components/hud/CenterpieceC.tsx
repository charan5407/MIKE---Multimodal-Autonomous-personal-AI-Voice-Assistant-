import React, { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { VoiceState } from '../../types';

interface CenterpieceCProps {
  voiceState: VoiceState;
  rms: number;
  lowPowerMode?: boolean;
}

export const CenterpieceC: React.FC<CenterpieceCProps> = ({
  voiceState,
  rms,
  lowPowerMode = false,
}) => {
  const meshRef = useRef<THREE.Mesh>(null);

  // Generate 3D curved "C" geometry using THREE.Shape and ExtrudeGeometry
  const geometry = useMemo(() => {
    const shape = new THREE.Shape();
    const outerRadius = 0.95;
    const innerRadius = 0.60;
    
    // Angles for the "C" opening on the right side:
    // Opens from ~35 deg to ~-35 deg (approx 0.6 rad to 5.68 rad)
    const startAngle = 0.65;
    const endAngle = Math.PI * 2 - 0.65;

    // Draw outer arc
    shape.absarc(0, 0, outerRadius, startAngle, endAngle, false);

    // Flat cap at top opening
    const innerEndX = innerRadius * Math.cos(endAngle);
    const innerEndY = innerRadius * Math.sin(endAngle);

    shape.lineTo(innerEndX, innerEndY);

    // Draw inner arc back to start
    shape.absarc(0, 0, innerRadius, endAngle, startAngle, true);

    // Flat cap at bottom opening
    const startX = outerRadius * Math.cos(startAngle);
    const startY = outerRadius * Math.sin(startAngle);
    shape.lineTo(startX, startY);

    const extrudeSettings: THREE.ExtrudeGeometryOptions = {
      depth: 0.28,
      bevelEnabled: true,
      bevelSegments: lowPowerMode ? 2 : 4,
      steps: 1,
      bevelSize: 0.05,
      bevelThickness: 0.05,
      curveSegments: lowPowerMode ? 24 : 48,
    };

    const geom = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geom.center(); // Center the pivot point
    return geom;
  }, [lowPowerMode]);

  // Color targets per state
  const stateColor = useMemo(() => {
    switch (voiceState) {
      case 'LISTENING':
        return new THREE.Color('#00f0ff'); // Intense electric cyan
      case 'THINKING':
        return new THREE.Color('#a855f7'); // Shimmering violet
      case 'SPEAKING':
        return new THREE.Color('#38bdf8'); // Radiant sky blue
      case 'STOPPED':
        return new THREE.Color('#ef4444'); // Crimson alert
      case 'ERROR':
        return new THREE.Color('#ff0033'); // Bright red flash
      case 'IDLE':
      default:
        return new THREE.Color('#00c8e0'); // Deep calm cyan
    }
  }, [voiceState]);

  // Frame animation: audio reaction, rotation, breathing glow
  useFrame((state, delta) => {
    if (!meshRef.current) return;

    const t = state.clock.getElapsedTime();

    // Base breathing scale + audio RMS pulse
    const baseBreath = 1.0 + Math.sin(t * 1.8) * 0.02;
    const audioPulse = Math.min(0.45, rms * 0.7);
    const targetScale = (baseBreath + audioPulse);

    // Smooth lerp scale
    meshRef.current.scale.lerp(
      new THREE.Vector3(targetScale, targetScale, targetScale),
      0.15
    );

    // State-specific motion
    if (voiceState === 'LISTENING') {
      meshRef.current.rotation.y = Math.sin(t * 3.0) * 0.15;
      meshRef.current.rotation.x = Math.cos(t * 2.5) * 0.08;
    } else if (voiceState === 'THINKING') {
      meshRef.current.rotation.y += delta * 1.5;
      meshRef.current.rotation.z = Math.sin(t * 4.0) * 0.05;
    } else if (voiceState === 'SPEAKING') {
      meshRef.current.rotation.y = Math.sin(t * 2.2) * 0.08;
      meshRef.current.rotation.x = Math.sin(t * 3.5) * 0.05;
    } else if (voiceState === 'STOPPED') {
      meshRef.current.rotation.set(0, 0, 0);
    } else {
      // IDLE gentle floating
      meshRef.current.rotation.y = Math.sin(t * 0.8) * 0.1;
      meshRef.current.rotation.x = Math.cos(t * 0.6) * 0.05;
    }

    // Dynamic emissive glow intensity
    const mat = meshRef.current.material as THREE.MeshPhysicalMaterial;
    if (mat) {
      const pulseIntensity = voiceState === 'LISTENING' 
        ? 0.7 + audioPulse * 1.2
        : voiceState === 'THINKING'
        ? 0.5 + Math.sin(t * 6.0) * 0.3
        : 0.35 + Math.sin(t * 2.0) * 0.15;

      mat.emissive.lerp(stateColor, 0.1);
      mat.emissiveIntensity = THREE.MathUtils.lerp(mat.emissiveIntensity, pulseIntensity, 0.1);
    }
  });

  return (
    <group>
      {/* Primary 3D Metallic "C" */}
      <mesh ref={meshRef} geometry={geometry}>
        <meshPhysicalMaterial
          color="#050b14"
          emissive={stateColor}
          emissiveIntensity={0.4}
          metalness={0.92}
          roughness={0.12}
          clearcoat={1.0}
          clearcoatRoughness={0.08}
          reflectivity={0.9}
        />
      </mesh>

      {/* Subtle Inner Glow Core Core PointLight */}
      <pointLight
        color={stateColor}
        intensity={voiceState === 'LISTENING' ? 4.0 + rms * 6.0 : 2.5}
        distance={4.0}
        decay={2.0}
        position={[0, 0, 0.5]}
      />
    </group>
  );
};
