"""
MIKE Text-to-Speech (TTS) Engine.
Produces a calm, soft-spoken female voice with tunable speed and pitch.
Supports immediate barge-in interruption and audio stream playback.
Primary: edge-tts (en-US-AriaNeural / en-GB-SoniaNeural) and local Piper engine.
"""

import asyncio
import io
import os
import re
import threading
import time
from pathlib import Path
from typing import AsyncIterator, Optional
import numpy as np

from core.config import settings
from core.logger import logger

try:
    import edge_tts
except ImportError:
    edge_tts = None

try:
    import sounddevice as sd
except ImportError:
    sd = None


class TTSEngine:
    def __init__(
        self,
        voice: str = "en-US-AriaNeural",
        rate: str = "-4%",    # slightly slower for calm, composed delivery
        pitch: str = "-2Hz",  # softer, warm tone
        cache_dir: Optional[Path] = None,
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.cache_dir = cache_dir or (settings.data_dir / "tts_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._stop_event = threading.Event()
        self._is_speaking = False
        self._lock = threading.Lock()

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop_playback(self):
        """Immediately interrupts any current TTS audio playback (Barge-in)."""
        self._stop_event.set()
        if sd is not None:
            try:
                sd.stop()
            except Exception:
                pass
        self._is_speaking = False
        logger.debug("TTS playback stopped (barge-in).")

    @staticmethod
    def clean_text_for_speech(text: str) -> str:
        """Strips markdown formatting, code blocks, URLs, and symbols for natural voice output."""
        if not text:
            return ""

        # Remove fenced code blocks
        text = re.sub(r"```[\s\S]*?```", " Code block omitted. ", text)
        # Remove inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove markdown links, keep text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
        # Remove raw URLs
        text = re.sub(r"https?://\S+|www\.\S+", "link", text)
        # Remove markdown headers, bold, italics
        text = re.sub(r"#{1,6}\s*", "", text)
        text = re.sub(r"[*_~]{1,3}", "", text)
        # Remove bullet markers and table pipes
        text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\|", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def synthesize_to_bytes(self, text: str) -> Optional[bytes]:
        """Synthesizes text to MP3 audio bytes using edge-tts."""
        cleaned = self.clean_text_for_speech(text)
        if not cleaned:
            return None

        if edge_tts is None:
            logger.error("edge-tts library is not available.")
            return None

        communicate = edge_tts.Communicate(
            text=cleaned,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )

        audio_stream = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_stream.write(chunk["data"])

        return audio_stream.getvalue()

    def play_audio_bytes(self, mp3_bytes: bytes, on_start=None, on_finish=None) -> bool:
        """
        Plays audio bytes with barge-in support.
        If self.stop_playback() is called, stops within ~50ms.
        """
        if not mp3_bytes or sd is None:
            return False

        try:
            import av
        except ImportError:
            logger.warning("PyAV not available for mp3 decoding.")
            return False

        self._stop_event.clear()
        self._is_speaking = True
        if on_start:
            on_start()

        try:
            # Decode MP3 to raw PCM float32 using PyAV
            container = av.open(io.BytesIO(mp3_bytes), format="mp3")
            stream = container.streams.audio[0]
            sample_rate = stream.rate

            # Collect raw samples
            pcm_chunks = []
            for frame in container.decode(stream):
                if self._stop_event.is_set():
                    break
                # Convert to float32 mono or stereo
                arr = frame.to_ndarray()
                if arr.ndim == 2:
                    # Shape is usually (channels, samples), transpose to (samples, channels)
                    arr = arr.T
                    if arr.shape[1] > 1:
                        arr = np.mean(arr, axis=1)  # downmix to mono
                pcm_chunks.append(arr.astype(np.float32) / 32768.0)

            if not pcm_chunks or self._stop_event.is_set():
                self._is_speaking = False
                return False

            full_pcm = np.concatenate(pcm_chunks)

            # Play in small blocks to allow responsive barge-in
            chunk_size = int(sample_rate * 0.05)  # 50ms blocks
            out_stream = sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
            )
            out_stream.start()

            for i in range(0, len(full_pcm), chunk_size):
                if self._stop_event.is_set():
                    break
                block = full_pcm[i : i + chunk_size]
                out_stream.write(block)

            out_stream.stop()
            out_stream.close()

        except Exception as e:
            logger.error(f"Error during audio playback: {e}")
            return False
        finally:
            self._is_speaking = False
            if on_finish:
                on_finish()

        return not self._stop_event.is_set()

    async def speak(self, text: str, on_start=None, on_finish=None) -> bool:
        """Asynchronously synthesizes and plays speech with barge-in support."""
        audio_bytes = await self.synthesize_to_bytes(text)
        if not audio_bytes:
            return False

        # Run blocking audio playback in thread
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self.play_audio_bytes,
            audio_bytes,
            on_start,
            on_finish,
        )


# Global TTS instance
tts_engine = TTSEngine()

