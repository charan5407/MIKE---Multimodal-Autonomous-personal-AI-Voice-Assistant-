"""
Keyboard, Clipboard, and Screenshot Automation Tools for MIKE.
Supports typing text, pressing hotkeys (undo, select all, copy/paste), and capturing screenshots.
"""

import time
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from core.config import settings
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import pyperclip
except ImportError:
    pyperclip = None

try:
    import pyautogui
except ImportError:
    pyautogui = None


class CopyTextArgs(BaseModel):
    text: str = Field(description="The text to copy to the Windows clipboard")


class CopyTextTool(BaseTool):
    name = "copy_text"
    description = "Copies text to the clipboard."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = CopyTextArgs

    async def execute(self, cancellation_token: CancellationToken, text: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if pyperclip is None:
            return ToolResult(success=False, error="pyperclip library not available.")

        pyperclip.copy(text)
        return ToolResult(success=True, output=f"Copied {len(text)} characters to clipboard.")


class PasteTextTool(BaseTool):
    name = "paste_text"
    description = "Retrieves the current text stored in the clipboard."
    tier = PermissionTier.TIER_A_SAFE

    async def execute(self, cancellation_token: CancellationToken) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if pyperclip is None:
            return ToolResult(success=False, error="pyperclip library not available.")

        content = pyperclip.paste()
        return ToolResult(success=True, output={"clipboard_text": content, "length": len(content)})


class TypeTextArgs(BaseModel):
    text: str = Field(description="The text string to type into the currently focused window")
    interval: float = Field(default=0.02, description="Typing speed interval in seconds per character")


class TypeTextTool(BaseTool):
    name = "type_text"
    description = "Types text into the currently active/focused window using simulated keystrokes."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = TypeTextArgs

    async def execute(self, cancellation_token: CancellationToken, text: str, interval: float = 0.02) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if pyautogui is None:
            return ToolResult(success=False, error="pyautogui library not available.")

        for char in text:
            cancellation_token.raise_if_cancelled()
            pyautogui.write(char)
            if interval > 0:
                time.sleep(interval)

        return ToolResult(success=True, output=f"Typed {len(text)} characters.")


class PressHotkeyArgs(BaseModel):
    keys: List[str] = Field(
        description="Key combination to press together, e.g. ['ctrl', 'c'], ['alt', 'tab'], ['ctrl', 'z'], ['win', 'd']"
    )


class PressHotkeyTool(BaseTool):
    name = "press_hotkey"
    description = "Simulates a keyboard hotkey combination (e.g. ['ctrl', 'c'], ['ctrl', 'v'], ['ctrl', 'z'], ['alt', 'tab'])."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = PressHotkeyArgs

    async def execute(self, cancellation_token: CancellationToken, keys: List[str]) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if pyautogui is None:
            return ToolResult(success=False, error="pyautogui library not available.")

        clean_keys = [k.lower().strip() for k in keys]
        pyautogui.hotkey(*clean_keys)
        return ToolResult(success=True, output=f"Pressed hotkey: {' + '.join(clean_keys)}")


class ScreenshotArgs(BaseModel):
    filename: Optional[str] = Field(default=None, description="Optional custom filename for screenshot")


class ScreenshotTool(BaseTool):
    name = "take_screenshot"
    description = "Captures a full screenshot of the laptop display and saves it to a local image file."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = ScreenshotArgs

    async def execute(self, cancellation_token: CancellationToken, filename: Optional[str] = None) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if pyautogui is None:
            return ToolResult(success=False, error="pyautogui library not available.")

        save_dir = settings.data_dir / "screenshots"
        save_dir.mkdir(parents=True, exist_ok=True)

        name = filename or f"screenshot_{int(time.time())}.png"
        file_path = save_dir / name

        try:
            img = pyautogui.screenshot()
            img.save(str(file_path))
            logger.info(f"Screenshot captured: {file_path}")
            return ToolResult(
                success=True,
                output={"path": str(file_path), "filename": name, "size": img.size},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to capture screenshot: {e}")
