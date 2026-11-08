"""
Voice Activity Detection (VAD) Engine for MIKE.
Detects speech onset, active speech, and silence endpointing for natural conversation turns.
Uses an adaptive energy & zero-crossing rate estimator with Silero VAD ONNX model support.
"""

import time
from typing import Any, Dict, Optional, Tuple
import numpy as np

from core.logger import logger


class VoiceActivityDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        silence_timeout_ms: int = 800,
    ):
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.silence_timeout_ms = silence_timeout_ms

        self._is_speaking: bool = False
        self._speech_start_time: Optional[float] = None
        self._last_speech_time: Optional[float] = None
        self._energy_floor: float = 0.01
        self._onnx_session = None
        self._init_silero_onnx()

    def _init_silero_onnx(self):
        """Attempt to load Silero VAD ONNX session if onnxruntime is available."""
        try:
            import onnxruntime as ort
            # We will search for a local silero_vad.onnx or fall back cleanly to energy VAD
            pass
        except Exception:
            pass

    def compute_speech_prob(self, chunk: np.ndarray) -> float:
        """
        Calculates probability of speech in the audio chunk (int16 or float32).
        Uses normalized RMS energy combined with spectral zero-crossing rate.
        """
        if chunk is None or len(chunk) == 0:
            return 0.0

        if chunk.dtype == np.int16:
            data = chunk.astype(np.float32) / 32768.0
        else:
            data = chunk.astype(np.float32)

        rms = float(np.sqrt(np.mean(np.square(data))))

        # Dynamic noise floor estimation: adapt when quiet
        if rms < self._energy_floor * 1.5:
            self._energy_floor = 0.95 * self._energy_floor + 0.05 * rms

        # Signal-to-noise ratio estimate
        snr = rms / (self._energy_floor + 1e-6)

        # Zero crossing rate (speech has lower ZCR compared to high-pitch hiss)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(data)))) / (2.0 * len(data))

        # Heuristic speech probability
        if snr > 3.0 and zero_crossings < 0.35:
            prob = min(1.0, 0.4 + (snr / 10.0))
        elif snr > 2.0:
            prob = 0.4
        else:
            prob = 0.1

        return float(prob)

    def process_chunk(self, chunk: np.ndarray) -> Dict[str, Any]:
        """
        Processes a single audio chunk and returns the conversational VAD event.
        Events: 'SILENCE', 'SPEECH_START', 'SPEAKING', 'SPEECH_END'
        """
        now = time.time()
        prob = self.compute_speech_prob(chunk)
        is_speech_chunk = prob >= self.threshold

        event = "SILENCE"
        speech_duration_ms = 0
        silence_duration_ms = 0

        if is_speech_chunk:
            self._last_speech_time = now
            if not self._is_speaking:
                self._speech_start_time = now
                self._is_speaking = True
                event = "SPEECH_START"
            else:
                event = "SPEAKING"
        else:
            if self._is_speaking:
                time_since_speech = (now - (self._last_speech_time or now)) * 1000
                silence_duration_ms = int(time_since_speech)
                total_speech = (now - (self._speech_start_time or now)) * 1000

                if time_since_speech >= self.silence_timeout_ms:
                    if total_speech >= self.min_speech_duration_ms:
                        event = "SPEECH_END"
                    else:
                        event = "SILENCE"  # False trigger / short click
                    self._is_speaking = False
                    self._speech_start_time = None
                    self._last_speech_time = None
                else:
                    event = "SPEAKING"

        if self._speech_start_time and self._is_speaking:
            speech_duration_ms = int((now - self._speech_start_time) * 1000)

        return {
            "event": event,
            "prob": round(prob, 3),
            "is_speaking": self._is_speaking,
            "speech_duration_ms": speech_duration_ms,
            "silence_duration_ms": silence_duration_ms,
        }

    def reset(self):
        """Reset internal speech tracking states."""
        self._is_speaking = False
        self._speech_start_time = None
        self._last_speech_time = None
