"""
Workstation Lock Tool for Windows (and macOS/Linux cross-platform fallback).
Executes ctypes.windll.user32.LockWorkStation() on Windows.
"""

import ctypes
import os
import subprocess
import sys
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class LockWorkstationTool(BaseTool):
    name = "lock_workstation"
    description = "Locks the computer workstation/laptop immediately."
    tier = PermissionTier.TIER_B_REVERSIBLE  # Logged action, directly executed when requested aloud

    async def execute(self, cancellation_token: CancellationToken) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        logger.info("Executing workstation lock command...")

        try:
            if sys.platform == "win32":
                # Windows native lock workstation API
                success = ctypes.windll.user32.LockWorkStation()
                if success != 0:
                    return ToolResult(success=True, output="Workstation locked successfully.")
                else:
                    return ToolResult(success=False, error="Failed to lock Windows workstation.")
            elif sys.platform == "darwin":
                # macOS lock display
                subprocess.run(["pmset", "displaysleepnow"], check=True)
                return ToolResult(success=True, output="macOS screen locked.")
            else:
                # Linux screensaver lock
                subprocess.run(["xdg-screensaver", "lock"], check=True)
                return ToolResult(success=True, output="Linux session locked.")
        except Exception as e:
            logger.error(f"Error locking workstation: {e}")
            return ToolResult(success=False, error=f"Lock workstation failed: {e}")

