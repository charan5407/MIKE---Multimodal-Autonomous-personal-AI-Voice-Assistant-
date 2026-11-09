"""
Vision Grounding Engine for MIKE.
Uses Gemini 2.0 Flash Vision to localize UI controls and targets from desktop screenshots.
Translates normalized [0, 1000] model coordinates to physical screen pixels.
Forms the core 'Observe' stage of the Observe-Act-Verify loop.
"""

import io
import json
import re
from typing import Any, Dict, Optional, Tuple
from PIL import Image
import pyautogui

from core.config import settings
from core.logger import logger


class VisionGrounder:
    """Vision-based GUI element grounding using Gemini Vision models."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self._api_key = api_key or settings.gemini_api_key
        self._model = model
        self._client = None
        if self._api_key and self._api_key.strip():
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.debug(f"Could not initialize VisionGrounder genai client: {e}")

    @property
    def is_available(self) -> bool:
        return bool(self._client is not None)

    def capture_screenshot(self) -> Image.Image:
        """Captures current desktop screen."""
        return pyautogui.screenshot()

    async def locate_target(
        self,
        target_description: str,
        screenshot: Optional[Image.Image] = None,
    ) -> Optional[Tuple[int, int, Dict[str, Any]]]:
        """
        Locates a UI element from a desktop screenshot using Gemini Vision grounding.
        Returns (pixel_x, pixel_y, metadata) or None if target cannot be found.
        """
        if not self.is_available:
            logger.warning("Gemini Vision Grounder is not available (GEMINI_API_KEY not configured).")
            return None

        if screenshot is None:
            screenshot = self.capture_screenshot()

        screen_w, screen_h = screenshot.size

        # Convert image to PNG bytes
        buffer = io.BytesIO()
        screenshot.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        prompt = (
            f"You are an expert GUI grounding and localization model for Windows 11.\n"
            f"Analyze this desktop screenshot and find the exact UI element matching: '{target_description}'.\n"
            f"Return ONLY a valid JSON object with the center coordinates in normalized range [0, 1000] for both X and Y:\n"
            f'{{\n'
            f'  "found": true,\n'
            f'  "x": <integer 0 to 1000>,\n'
            f'  "y": <integer 0 to 1000>,\n'
            f'  "description": "<brief description of the located element>",\n'
            f'  "confidence": <float 0.0 to 1.0>\n'
            f'}}\n\n'
            f"If the element is not visible or cannot be found, return:\n"
            f'{{\n'
            f'  "found": false,\n'
            f'  "reason": "<reason why element is not found>"\n'
            f'}}\n'
            f"Do not include any text before or after the JSON."
        )

        try:
            from google.genai import types

            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            response = self._client.models.generate_content(
                model=self._model,
                contents=[image_part, prompt],
            )

            raw_text = response.text or ""
            # Extract JSON block
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                logger.warning(f"No JSON found in vision grounding response: {raw_text}")
                return None

            data = json.loads(json_match.group(0))
            if not data.get("found"):
                logger.info(f"Vision model reported target '{target_description}' not found: {data.get('reason')}")
                return None

            norm_x = float(data.get("x", 500))
            norm_y = float(data.get("y", 500))

            # Convert normalized [0, 1000] to actual screen pixel coordinates
            pixel_x = int(round((norm_x / 1000.0) * screen_w))
            pixel_y = int(round((norm_y / 1000.0) * screen_h))

            # Clamp within screen bounds
            pixel_x = max(0, min(screen_w - 1, pixel_x))
            pixel_y = max(0, min(screen_h - 1, pixel_y))

            logger.info(
                f"VisionGrounder successfully located '{target_description}' at pixel ({pixel_x}, {pixel_y}) "
                f"[norm: {norm_x}, {norm_y}], confidence: {data.get('confidence', 1.0)}"
            )

            return pixel_x, pixel_y, {
                "source": "gemini_vision",
                "normalized": [norm_x, norm_y],
                "confidence": data.get("confidence", 1.0),
                "description": data.get("description", target_description),
            }

        except Exception as e:
            logger.error(f"Error during vision grounding query: {e}")
            return None


# Global vision grounder instance
vision_grounder = VisionGrounder()

