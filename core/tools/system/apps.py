"""
Application Management Tools for Windows.
Allows opening, closing, and listing applications on the system safely.
"""

import os
import subprocess
import sys
from typing import List, Optional
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import psutil
except ImportError:
    psutil = None

# Common Windows App aliases & executable mapping
APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "msedge",
    "ms edge": "msedge",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "spotify": "spotify",
    "whatsapp": "whatsapp:",
    "terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
}


class OpenAppArgs(BaseModel):
    app_name: str = Field(description="Name or alias of the application to open, e.g. 'notepad', 'chrome', 'vscode'")


class OpenAppTool(BaseTool):
    name = "open_app"
    description = "Opens an application by name (e.g. 'notepad', 'calculator', 'chrome', 'vscode', 'spotify')."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = OpenAppArgs

    async def execute(self, cancellation_token: CancellationToken, app_name: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        norm_name = app_name.lower().strip()
        target = APP_MAP.get(norm_name, norm_name)

        logger.info(f"Opening application: {norm_name} -> {target}")

        try:
            if sys.platform == "win32":
                # Check if it's a URI scheme (e.g. whatsapp:)
                if target.endswith(":"):
                    os.startfile(target)
                else:
                    try:
                        subprocess.Popen(target, shell=True)
                    except Exception:
                        os.startfile(target)
            else:
                subprocess.Popen([target])

            return ToolResult(
                success=True,
                output=f"Opened application: {app_name}.",
                reversible=True,
                rollback_data={"app_name": app_name},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to open '{app_name}': {e}")


class CloseAppArgs(BaseModel):
    app_name: str = Field(description="Name of the application or process to close")


class CloseAppTool(BaseTool):
    name = "close_app"
    description = "Closes a running application by terminating its processes safely."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = CloseAppArgs

    async def execute(self, cancellation_token: CancellationToken, app_name: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if psutil is None:
            return ToolResult(success=False, error="psutil library not available.")

        norm_name = app_name.lower().strip().replace(".exe", "")
        terminated_count = 0

        try:
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    pname = (proc.info["name"] or "").lower().replace(".exe", "")
                    if norm_name in pname:
                        proc.terminate()
                        terminated_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if terminated_count > 0:
                return ToolResult(success=True, output=f"Closed {terminated_count} process(es) for '{app_name}'.")
            else:
                return ToolResult(success=False, error=f"No running process found matching '{app_name}'.")
        except Exception as e:
            return ToolResult(success=False, error=f"Error closing '{app_name}': {e}")


class ListAppsTool(BaseTool):
    name = "list_running_apps"
    description = "Lists currently active user applications running on the laptop."
    tier = PermissionTier.TIER_A_SAFE

    async def execute(self, cancellation_token: CancellationToken) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        if psutil is None:
            return ToolResult(success=False, error="psutil library not available.")

        apps = set()
        try:
            for proc in psutil.process_iter(["name"]):
                try:
                    name = proc.info["name"]
                    if name and name.endswith(".exe"):
                        name_clean = name[:-4]
                        # Filter out basic background windows services
                        if name_clean.lower() not in ["svchost", "csrss", "smss", "wininit", "services", "lsass", "explorer"]:
                            apps.add(name_clean)
                except Exception:
                    continue

            sorted_apps = sorted(list(apps))[:25]
            return ToolResult(success=True, output={"running_apps": sorted_apps, "count": len(sorted_apps)})
        except Exception as e:
            return ToolResult(success=False, error=f"Error listing running apps: {e}")
