"""
Speech-to-Text (STT) Engine using faster-whisper.
Runs locally with NVIDIA CUDA GPU acceleration (fallback to CPU int8).
Transcribes audio buffers and detects user stop commands.
"""

import time
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from core.config import settings
from core.logger import logger

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class STTEngine:
    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "auto",
        compute_type: str = "auto",
        download_root: Optional[Path] = None,
    ):
        self.model_size = model_size
        self.download_root = download_root or (settings.models_dir / "whisper")
        self.download_root.mkdir(parents=True, exist_ok=True)

        self._model: Optional[WhisperModel] = None
        self._device = device
        self._compute_type = compute_type
        self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    def load_model(self):
        """Loads faster-whisper model onto CUDA GPU (or CPU fallback)."""
        if self._is_loaded and self._model is not None:
            return

        if WhisperModel is None:
            raise RuntimeError("faster-whisper is not installed.")

        # Determine compute target
        device = self._device
        compute_type = self._compute_type

        if device == "auto":
            try:
                # Check for CUDA via ctranslate2
                import ctranslate2
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
                    compute_type = "float16" if compute_type == "auto" else compute_type
                    logger.info(f"NVIDIA GPU detected with {ctranslate2.get_cuda_device_count()} CUDA device(s).")
                else:
                    device = "cpu"
                    compute_type = "int8" if compute_type == "auto" else compute_type
            except Exception as e:
                logger.warning(f"CUDA check error: {e}. Falling back to CPU.")
                device = "cpu"
                compute_type = "int8"

        logger.info(f"Loading faster-whisper ({self.model_size}) on {device.upper()} [{compute_type}]...")
        start_time = time.perf_counter()

        try:
            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
                download_root=str(self.download_root),
            )
            self._is_loaded = True
            load_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"faster-whisper loaded successfully in {load_ms:.0f}ms.")
        except Exception as e:
            if device == "cuda":
                logger.warning(f"Failed to load on CUDA: {e}. Retrying on CPU [int8]...")
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                    download_root=str(self.download_root),
                )
                self._is_loaded = True
                logger.info("faster-whisper loaded on CPU fallback.")
            else:
                raise

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> Tuple[str, float]:
        """
        Transcribes a 1D numpy array of audio (16kHz).
        Returns: (transcribed_text, latency_ms)
        """
        if audio is None or len(audio) == 0:
            return "", 0.0

        if not self._is_loaded:
            self.load_model()

        # Convert int16 audio to float32 normalized in [-1.0, 1.0]
        if audio.dtype == np.int16:
            audio_float = audio.astype(np.float32) / 32768.0
        else:
            audio_float = audio.astype(np.float32)

        audio_float = np.ascontiguousarray(audio_float.flatten(), dtype=np.float32)

        start_time = time.perf_counter()
        domain_prompt = (
            "MIKE AI desktop assistant for Charan. Python, VS Code, Visual Studio Code, "
            "linked list, bubble sort, binary search, algorithms, data structures, "
            "YouTube, Spotify, WhatsApp, open application, system volume, "
            "how many languages do you speak, what can you do, who are you."
        )

        segments, info = self._model.transcribe(
            audio_float,
            beam_size=2,
            language="en",
            temperature=0.0,
            initial_prompt=domain_prompt,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            compression_ratio_threshold=2.4,
            vad_filter=False,  # We handle VAD upstream for low latency
        )

        texts = [seg.text.strip() for seg in segments if seg.text.strip()]
        full_text = " ".join(texts).strip()

        # Phonetic corrections for common assistant mishearings
        if full_text:
            import re
            full_text = re.sub(r"\b(?:mic|mack|maik)\b", "Mike", full_text, flags=re.IGNORECASE)
            full_text = re.sub(r"\b(?:piece\s+code|peace\s+code)\b", "VS Code", full_text, flags=re.IGNORECASE)

        latency_ms = (time.perf_counter() - start_time) * 1000

        return full_text, round(latency_ms, 2)


# Global STT instance
stt_engine = STTEngine()
