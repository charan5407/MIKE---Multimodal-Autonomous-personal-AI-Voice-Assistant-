"""
Display Screen Brightness Control Tool.
Uses screen_brightness_control with cross-platform fallback.
"""

from pydantic import BaseModel, Field
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import screen_brightness_control as sbc
except ImportError:
    sbc = None


class SetBrightnessArgs(BaseModel):
    level: int = Field(ge=0, le=100, description="Brightness percentage from 0 to 100")


class SetBrightnessTool(BaseTool):
    name = "set_brightness"
    description = "Sets the laptop/monitor display brightness level (0 to 100 percent)."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = SetBrightnessArgs

    async def execute(self, cancellation_token: CancellationToken, level: int) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if sbc is None:
            return ToolResult(success=False, error="screen_brightness_control library not available.")

        try:
            sbc.set_brightness(level)
            return ToolResult(success=True, output=f"Brightness set to {level}%.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error adjusting brightness: {e}")


class GetBrightnessTool(BaseTool):
    name = "get_brightness"
    description = "Retrieves current laptop display brightness percentage."
    tier = PermissionTier.TIER_A_SAFE

    async def execute(self, cancellation_token: CancellationToken) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if sbc is None:
            return ToolResult(success=False, error="screen_brightness_control library not available.")

        try:
            current = sbc.get_brightness()
            val = current[0] if isinstance(current, list) and current else current
            return ToolResult(success=True, output=f"Current display brightness is {val}%.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error reading brightness: {e}")

