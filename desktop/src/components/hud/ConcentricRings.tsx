import React, { useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { VoiceState } from '../../types';

interface ConcentricRingsProps {
  voiceState: VoiceState;
  rms: number;
}

export const ConcentricRings: React.FC<ConcentricRingsProps> = ({ voiceState, rms }) => {
  const ring1Ref = useRef<THREE.Group>(null);
  const ring2Ref = useRef<THREE.Group>(null);
  const ring3Ref = useRef<THREE.Group>(null);

  // Pick color matching assistant state
  const ringColor = React.useMemo(() => {
    switch (voiceState) {
      case 'LISTENING':
        return new THREE.Color('#00f0ff');
      case 'THINKING':
        return new THREE.Color('#c084fc');
      case 'SPEAKING':
        return new THREE.Color('#38bdf8');
      case 'STOPPED':
        return new THREE.Color('#ef4444');
      case 'ERROR':
        return new THREE.Color('#f43f5e');
      case 'IDLE':
      default:
        return new THREE.Color('#00c8e0');
    }
  }, [voiceState]);

  useFrame((_, delta) => {
    if (!ring1Ref.current || !ring2Ref.current || !ring3Ref.current) return;

    // Determine speed multipliers
    let speedMult = 0.4;
    if (voiceState === 'LISTENING') speedMult = 1.6 + rms * 3.0;
    else if (voiceState === 'THINKING') speedMult = 2.8;
    else if (voiceState === 'SPEAKING') speedMult = 1.2;

    // Ring 1: Clockwise Z rotation with subtle tilt
    ring1Ref.current.rotation.z += delta * 0.4 * speedMult;
    ring1Ref.current.rotation.x = Math.sin(ring1Ref.current.rotation.z * 0.5) * 0.15;

    // Ring 2: Gyroscope tilted counter-clockwise
    ring2Ref.current.rotation.y -= delta * 0.55 * speedMult;
    ring2Ref.current.rotation.z += delta * 0.25 * speedMult;

    // Ring 3: Inner fast orbit ring
    ring3Ref.current.rotation.x += delta * 0.65 * speedMult;
    ring3Ref.current.rotation.y += delta * 0.35 * speedMult;

    // Stopped collapse animation
    if (voiceState === 'STOPPED') {
      const collapseTarget = new THREE.Vector3(0.7, 0.7, 0.7);
      ring1Ref.current.scale.lerp(collapseTarget, 0.1);
      ring2Ref.current.scale.lerp(collapseTarget, 0.1);
      ring3Ref.current.scale.lerp(collapseTarget, 0.1);
    } else {
      const normalTarget = new THREE.Vector3(1, 1, 1);
      ring1Ref.current.scale.lerp(normalTarget, 0.1);
      ring2Ref.current.scale.lerp(normalTarget, 0.1);
      ring3Ref.current.scale.lerp(normalTarget, 0.1);
    }
  });

  return (
    <group>
      {/* Outer Segmented Ring 1 */}
      <group ref={ring1Ref}>
        <mesh>
          <torusGeometry args={[2.35, 0.016, 16, 100]} />
          <meshStandardMaterial
            color="#05101a"
            emissive={ringColor}
            emissiveIntensity={0.65}
            roughness={0.2}
            metalness={0.8}
          />
        </mesh>
        {/* Decorative Orbital Nodes */}
        {[0, 90, 180, 270].map((deg, i) => {
          const rad = (deg * Math.PI) / 180;
          return (
            <mesh key={i} position={[2.35 * Math.cos(rad), 2.35 * Math.sin(rad), 0]}>
              <sphereGeometry args={[0.045, 12, 12]} />
              <meshBasicMaterial color={ringColor} />
            </mesh>
          );
        })}
      </group>

      {/* Middle Gyroscope Ring 2 (Tilted) */}
      <group ref={ring2Ref} rotation={[Math.PI / 4, 0, Math.PI / 6]}>
        <mesh>
          <torusGeometry args={[1.88, 0.02, 16, 90]} />
          <meshStandardMaterial
            color="#030810"
            emissive={ringColor}
            emissiveIntensity={0.8}
            roughness={0.15}
            metalness={0.9}
          />
        </mesh>
        {/* Orbital Satellite Spheres */}
        {[45, 165, 285].map((deg, i) => {
          const rad = (deg * Math.PI) / 180;
          return (
            <mesh key={i} position={[1.88 * Math.cos(rad), 1.88 * Math.sin(rad), 0]}>
              <sphereGeometry args={[0.04, 12, 12]} />
              <meshBasicMaterial color={ringColor} />
            </mesh>
          );
        })}
      </group>

      {/* Inner Fast Orbit Ring 3 */}
      <group ref={ring3Ref} rotation={[-Math.PI / 3, Math.PI / 4, 0]}>
        <mesh>
          <torusGeometry args={[1.42, 0.018, 16, 80]} />
          <meshStandardMaterial
            color="#05101a"
            emissive={ringColor}
            emissiveIntensity={0.9}
            roughness={0.1}
            metalness={0.9}
          />
        </mesh>
        {/* Small Dual Nodes */}
        <mesh position={[1.42, 0, 0]}>
          <sphereGeometry args={[0.05, 12, 12]} />
          <meshBasicMaterial color={ringColor} />
        </mesh>
        <mesh position={[-1.42, 0, 0]}>
          <sphereGeometry args={[0.05, 12, 12]} />
          <meshBasicMaterial color={ringColor} />
        </mesh>
      </group>
    </group>
  );
};

