"""
Multimodal Vision & Image Generation Tools for MIKE.
1. Text-to-Image Generation (Flux / SDXL via Pollinations Free Engine - 0 keys needed).
2. Image Understanding & Vision QA (Gemini 3.1 Flash-Lite / Vision Model).
"""

import base64
import os
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional
from PIL import Image
from pydantic import BaseModel, Field

from core.config import settings
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class GenerateImageArgs(BaseModel):
    prompt: str = Field(description="Visual description of the image to create, e.g. 'a solar powered city at sunset illustration'")
    width: Optional[int] = Field(default=1024, description="Width in pixels")
    height: Optional[int] = Field(default=1024, description="Height in pixels")


class GenerateImageTool(BaseTool):
    name = "generate_image"
    description = "Generates high-definition artwork, illustrations, or photos from text prompts (Text-to-Image)."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = GenerateImageArgs

    async def execute(self, cancellation_token: CancellationToken, prompt: str = "", width: int = 1024, height: int = 1024, **kwargs) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        clean_prompt = prompt.strip()
        if not clean_prompt:
            return ToolResult(success=False, error="Empty prompt provided.")

        clean_slug = re.sub(r"[^\w\s-]", "", clean_prompt.lower())
        clean_slug = re.sub(r"\s+", "_", clean_slug)[:25]
        timestamp = int(time.time())
        filename = f"gen_{timestamp}_{clean_slug}.jpg"

        out_dir = settings.data_dir / "generated_images"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / filename

        encoded = urllib.parse.quote(clean_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&model=flux"

        logger.info(f"Generating image via Pollinations AI: '{clean_prompt}'...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=45) as response:
                img_data = response.read()

            file_path.write_bytes(img_data)
            logger.info(f"Image generated and saved: {file_path} ({len(img_data)} bytes)")

            media_url = f"http://127.0.0.1:8765/media/{filename}"

            # Open image in default Windows Photo Viewer so Charan sees it immediately
            try:
                import sys
                if sys.platform == "win32":
                    os.startfile(str(file_path.resolve()))
            except Exception as e:
                logger.debug(f"Could not open image in viewer: {e}")

            return ToolResult(
                success=True,
                output=f"I have created the illustration for **{clean_prompt}**:\n\n![{clean_prompt}]({media_url})",
                data={
                    "file_path": str(file_path.resolve()),
                    "prompt": clean_prompt,
                    "url": media_url,
                    "filename": filename,
                    "size_bytes": len(img_data),
                }
            )
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return ToolResult(success=False, error=f"Could not generate image: {e}")


class ShowLatestImageArgs(BaseModel):
    query: Optional[str] = Field(default=None, description="Optional prompt query")


class ShowLatestImageTool(BaseTool):
    name = "show_latest_image"
    description = "Displays and opens the latest generated image or illustration on screen."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ShowLatestImageArgs

    async def execute(self, cancellation_token: CancellationToken, **kwargs) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        out_dir = settings.data_dir / "generated_images"
        if not out_dir.exists():
            return ToolResult(success=False, error="No generated images found.")

        imgs = sorted(list(out_dir.glob("*.jpg")) + list(out_dir.glob("*.png")), key=lambda f: f.stat().st_mtime, reverse=True)
        if not imgs:
            return ToolResult(success=False, error="No generated images found in library.")

        latest = imgs[0]
        # Open in default Windows viewer
        try:
            import sys
            if sys.platform == "win32":
                os.startfile(str(latest.resolve()))
        except Exception as e:
            logger.debug(f"Could not open image in viewer: {e}")

        media_url = f"http://127.0.0.1:8765/media/{latest.name}"
        clean_title = latest.stem.replace("gen_", "").replace("_", " ").title()

        return ToolResult(
            success=True,
            output=f"Here is your generated image for **{clean_title}**:\n\n![{clean_title}]({media_url})",
            data={"url": media_url, "path": str(latest.resolve())}
        )


class AnalyzeImageArgs(BaseModel):
    query: str = Field(description="Question about the image or screen, e.g. 'what warning is visible on the machine label' or 'describe what is on my screen'")
    image_path: Optional[str] = Field(default=None, description="Path to image file. If omitted or 'screen', captures the active desktop screen.")


class AnalyzeImageTool(BaseTool):
    name = "analyze_image"
    description = "Analyzes photos, labels, diagrams, or the current desktop screen to answer questions (Vision QA / Perception)."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = AnalyzeImageArgs

    async def execute(self, cancellation_token: CancellationToken, query: str = "", image_path: Optional[str] = None, **kwargs) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        clean_query = query.strip()
        img_target = (image_path or "").strip()

        # Capture desktop screen if requested or if path not given
        if not img_target or img_target.lower() in ["screen", "desktop", "current screen"]:
            try:
                import pyautogui
                screenshot_dir = settings.data_dir / "screenshots"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                screen_path = screenshot_dir / f"screen_{int(time.time())}.png"
                shot = pyautogui.screenshot()
                shot.save(str(screen_path))
                img_target = str(screen_path)
                logger.info(f"Captured screen for visual analysis: {img_target}")
            except Exception as e:
                return ToolResult(success=False, error=f"Failed to capture desktop screen: {e}")

        target_file = Path(img_target)
        if not target_file.exists():
            return ToolResult(success=False, error=f"Image file not found: {img_target}")

        # Run vision inference with Gemini 3.1 Flash-Lite
        try:
            from google import genai
            client = genai.Client(api_key=settings.gemini_api_key)
            img = Image.open(str(target_file))

            system_instruction = (
                "You are MIKE's visual perception engine. Examine the image carefully. "
                "Answer Charan's question accurately, noting text, warnings, diagrams, or objects."
            )
            res = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=[system_instruction, clean_query, img]
            )
            analysis = res.text.strip()
            return ToolResult(
                success=True,
                output=analysis,
                data={"analysis": analysis, "image_path": str(target_file)}
            )
        except Exception as e:
            logger.error(f"Vision analysis failed: {e}")
            return ToolResult(success=False, error=f"Vision perception error: {e}")
