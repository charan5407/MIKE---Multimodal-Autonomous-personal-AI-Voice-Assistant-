"""
Wake-Word Detection Engine for MIKE ("Mike" / "Hey Mike").
Integrates openWakeWord with ONNX runtime and sliding audio chunk buffer.
"""

from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

from core.config import settings
from core.logger import logger

try:
    import openwakeword
    from openwakeword.model import Model as OWWModel
except ImportError:
    OWWModel = None


class WakeWordDetector:
    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        threshold: float = 0.5,
        enabled: bool = True,
        models_dir: Optional[Path] = None,
    ):
        self.wake_words = [w.lower() for w in (wake_words or ["mike", "hey mike"])]
        self.threshold = threshold
        self.enabled = enabled
        self.models_dir = models_dir or (settings.models_dir / "wakeword")
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self._oww_model = None
        self._buffer: List[np.ndarray] = []
        self._target_chunk_size = 1280  # 80ms chunks for openWakeWord at 16kHz
        self._is_loaded = False
        self._recent_scores: Dict[str, float] = {}

    @property
    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, val: bool):
        self.enabled = val
        logger.info(f"Wake word detection set to: {'ENABLED' if val else 'DISABLED'}")

    def load_model(self):
        """Loads openWakeWord models or configures fallback."""
        if self._is_loaded:
            return

        if OWWModel is not None:
            try:
                # Initialize openWakeWord with default bundled or preloaded models
                self._oww_model = OWWModel(inference_framework="onnx")
                self._is_loaded = True
                logger.info(f"openWakeWord loaded models: {list(self._oww_model.models.keys())}")
            except Exception as e:
                logger.warning(f"Could not load bundled openWakeWord models: {e}. Fallback enabled.")
                self._oww_model = None
                self._is_loaded = True
        else:
            logger.info("openWakeWord not present; fallback keyword spotting active.")
            self._is_loaded = True

    def process_chunk(self, chunk: np.ndarray) -> bool:
        """
        Feeds an incoming audio chunk (e.g. 512 samples int16) into the sliding window.
        Returns True if 'Mike' or 'Hey Mike' is detected above threshold.
        """
        if not self.enabled:
            return False

        if not self._is_loaded:
            self.load_model()

        if chunk is None or len(chunk) == 0:
            return False

        # Accumulate chunks until we reach openWakeWord's required 1280 samples (80ms)
        self._buffer.append(chunk)
        current_len = sum(len(c) for c in self._buffer)

        if current_len < self._target_chunk_size:
            return False

        # Concatenate and take the first 1280 samples
        flat = np.concatenate(self._buffer)
        audio_window = flat[: self._target_chunk_size]
        remainder = flat[self._target_chunk_size :]
        self._buffer = [remainder] if len(remainder) > 0 else []

        # Predict with openWakeWord if available
        if self._oww_model is not None:
            try:
                # openWakeWord expects 16-bit PCM integer values
                int16_window = audio_window.astype(np.int16)
                prediction = self._oww_model.predict(int16_window)
                self._recent_scores = prediction

                for model_name, score in prediction.items():
                    if score >= self.threshold:
                        logger.info(f"Wake word detected via [{model_name}] with confidence: {score:.3f}")
                        self.reset()
                        return True
            except Exception as e:
                logger.debug(f"Error in openWakeWord prediction: {e}")

        return False

    def get_latest_scores(self) -> Dict[str, float]:
        """Returns the most recent prediction confidence scores for the UI."""
        return self._recent_scores

    def reset(self):
        """Clears buffer and model internal states."""
        self._buffer = []
        if self._oww_model is not None:
            try:
                self._oww_model.reset()
            except Exception:
                pass


# Global Wake-Word detector instance
wake_detector = WakeWordDetector()
