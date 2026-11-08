"""
MIKE Real-time Audio Stream Manager.
Captures microphone input and streams audio chunks for VAD, Wake-Word, and STT.
Also provides live RMS amplitude for the 3D HUD orb.
"""

import queue
import time
from typing import Any, Dict, List, Optional
import numpy as np

from core.logger import logger

try:
    import sounddevice as sd
except ImportError:
    sd = None


class AudioStreamManager:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 512,  # 32ms chunks at 16kHz
        device_index: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device_index = device_index

        self._audio_queue: queue.Queue = queue.Queue(maxsize=100)
        self._stream: Optional[Any] = None
        self._is_running: bool = False
        self._current_rms: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def current_rms(self) -> float:
        """Normalized RMS amplitude (0.0 to 1.0) for visualizer/HUD."""
        return self._current_rms

    @staticmethod
    def list_input_devices() -> List[Dict[str, Any]]:
        """Lists available microphone input devices."""
        if sd is None:
            return []
        devices = []
        try:
            for idx, dev in enumerate(sd.query_devices()):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name", f"Microphone {idx}"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 16000),
                    })
        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")
        return devices

    def _audio_callback(self, indata, frames, time_info, status):
        """Internal callback invoked by sounddevice for each audio buffer."""
        if status and status.input_overflow:
            # Drop or ignore frame on buffer overflow
            pass

        # Calculate RMS amplitude for UI / HUD
        data_float = indata.astype(np.float32)
        rms = np.sqrt(np.mean(np.square(data_float)))
        # Normalize roughly between 0.0 and 1.0
        self._current_rms = float(min(1.0, rms * 15.0))

        # Flatten mono channel and copy to prevent buffer overwrite
        chunk = indata[:, 0].copy()
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            # Discard oldest chunk if queue full
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.put_nowait(chunk)
            except Exception:
                pass

    def start(self):
        """Starts real-time microphone recording stream."""
        if self._is_running:
            return

        if sd is None:
            raise RuntimeError("sounddevice is not installed or available.")

        try:
            self._audio_queue = queue.Queue(maxsize=100)
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.chunk_size,
                device=self.device_index,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_running = True
            logger.info(f"Microphone audio stream started (Rate: {self.sample_rate}Hz, Block: {self.chunk_size})")
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self._is_running = False
            raise

    def stop(self):
        """Stops the audio recording stream."""
        if not self._is_running:
            return

        self._is_running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error closing audio stream: {e}")
            finally:
                self._stream = None

        self._current_rms = 0.0
        logger.info("Microphone audio stream stopped.")

    def read_chunk(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """Reads a single chunk (int16 numpy array) from the queue."""
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        """Clears all pending audio chunks in the queue."""
        with self._audio_queue.mutex:
            self._audio_queue.queue.clear()
