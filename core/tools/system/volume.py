"""
Windows Master Volume Control Tool using modern pycaw.
Supports getting volume, setting volume (0-100), and toggling mute.
"""

from typing import Optional
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import comtypes
    from pycaw.pycaw import AudioUtilities
except ImportError:
    AudioUtilities = None


def _get_volume_control():
    if AudioUtilities is None:
        return None
    try:
        # Initialize COM on the current thread
        try:
            comtypes.CoInitialize()
        except Exception:
            pass

        device = AudioUtilities.GetSpeakers()
        if device is None:
            return None

        # Modern pycaw exposes EndpointVolume property on AudioDevice
        if hasattr(device, "EndpointVolume"):
            return device.EndpointVolume

        # Legacy fallback
        if hasattr(device, "Activate"):
            from comtypes import CLSCTX_ALL
            import ctypes
            from pycaw.pycaw import IAudioEndpointVolume
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            return ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))

        return None
    except Exception as e:
        logger.debug(f"Failed to access pycaw master volume interface: {e}")
        return None


class SetVolumeArgs(BaseModel):
    level: int = Field(ge=0, le=100, description="Volume level from 0 to 100")


class SetVolumeTool(BaseTool):
    name = "set_volume"
    description = "Sets the Windows master audio volume level (0 to 100 percent)."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = SetVolumeArgs

    async def execute(self, cancellation_token: CancellationToken, level: int) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        control = _get_volume_control()
        if not control:
            return ToolResult(success=False, error="Windows audio interface unavailable.")

        try:
            scalar = max(0.0, min(1.0, level / 100.0))
            control.SetMasterVolumeLevelScalar(scalar, None)
            # If muted, unmute automatically when adjusting volume
            if control.GetMute():
                control.SetMute(0, None)
            return ToolResult(success=True, output=f"Volume set to {level}%.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error setting volume: {e}")


class GetVolumeTool(BaseTool):
    name = "get_volume"
    description = "Retrieves the current master audio volume level and mute status."
    tier = PermissionTier.TIER_A_SAFE

    async def execute(self, cancellation_token: CancellationToken) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        control = _get_volume_control()
        if not control:
            return ToolResult(success=False, error="Windows audio interface unavailable.")

        try:
            current_scalar = control.GetMasterVolumeLevelScalar()
            is_muted = bool(control.GetMute())
            percent = int(round(current_scalar * 100))
            status_text = f"Current volume is {percent}%" + (" (Muted)" if is_muted else "")
            return ToolResult(success=True, output={"level": percent, "is_muted": is_muted, "text": status_text})
        except Exception as e:
            return ToolResult(success=False, error=f"Error reading volume: {e}")


class ToggleMuteArgs(BaseModel):
    mute: Optional[bool] = Field(default=None, description="True to mute, False to unmute, None to toggle")


class ToggleMuteTool(BaseTool):
    name = "toggle_mute"
    description = "Mutes or unmutes the Windows master audio volume."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ToggleMuteArgs

    async def execute(self, cancellation_token: CancellationToken, mute: Optional[bool] = None) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        control = _get_volume_control()
        if not control:
            return ToolResult(success=False, error="Windows audio interface unavailable.")

        try:
            current_mute = bool(control.GetMute())
            new_mute = not current_mute if mute is None else mute
            control.SetMute(1 if new_mute else 0, None)
            state_str = "Muted" if new_mute else "Unmuted"
            return ToolResult(success=True, output=f"Audio {state_str}.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error toggling mute: {e}")
