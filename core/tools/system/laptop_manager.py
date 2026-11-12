"""
Complete Laptop & Application Management Tool for Windows 11.
Allows MIKE to launch, control, and inspect all applications and system states on Charan's laptop.
"""

import os
import subprocess
import sys
from typing import Optional
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import psutil
except ImportError:
    psutil = None


class LaptopManagerArgs(BaseModel):
    action: str = Field(description="Action to perform: 'launch', 'close', 'list_apps', 'system_stats', 'lock', 'screenshot'")
    target: Optional[str] = Field(default=None, description="Target app name or process name (e.g. 'vscode', 'chrome', 'spotify', 'task manager')")


class LaptopManagerTool(BaseTool):
    name = "manage_laptop"
    description = "Provides complete control over laptop applications, processes, windows, and system health."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = LaptopManagerArgs

    async def execute(self, cancellation_token: CancellationToken, action: str = "system_stats", target: Optional[str] = None, **kwargs) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        act = action.lower().strip()
        tgt = (target or "").lower().strip()

        if act == "list_apps":
            if not psutil:
                return ToolResult(success=False, error="psutil library is not available.")
            procs = []
            for p in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
                try:
                    name = p.info['name']
                    if name.endswith('.exe') and not name.lower().startswith(('svchost', 'system', 'registry')):
                        procs.append(name.replace('.exe', ''))
                except Exception:
                    pass
            unique_apps = sorted(list(set(procs)))[:25]
            return ToolResult(
                success=True,
                output=f"Currently running applications ({len(unique_apps)} detected): {', '.join(unique_apps[:15])}...",
                data={"apps": unique_apps}
            )

        elif act == "system_stats":
            if not psutil:
                return ToolResult(success=False, error="psutil library is not available.")
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            bat_str = f"{battery.percent}% ({'Plugged in' if battery.power_plugged else 'On Battery'})" if battery else "AC Desktop"

            stats_msg = (
                f"💻 **Laptop Health & System Resources**:\n"
                f"• **CPU Utilization**: {cpu}%\n"
                f"• **RAM Memory**: {mem.percent}% ({round(mem.used / (1024**3), 1)}GB / {round(mem.total / (1024**3), 1)}GB)\n"
                f"• **Battery Status**: {bat_str}"
            )
            return ToolResult(success=True, output=stats_msg, data={"cpu": cpu, "memory": mem.percent, "battery": bat_str})

        elif act in ["launch", "open"]:
            if not tgt:
                return ToolResult(success=False, error="Please specify which app you want me to launch.")
            from core.tools.system.apps import OpenAppTool
            tool = OpenAppTool()
            return await tool.execute(cancellation_token, app_name=tgt)

        elif act in ["close", "kill", "terminate"]:
            if not tgt:
                return ToolResult(success=False, error="Please specify which app you want me to close.")
            from core.tools.system.apps import CloseAppTool
            tool = CloseAppTool()
            return await tool.execute(cancellation_token, app_name=tgt)

        elif act == "lock":
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return ToolResult(success=True, output="Laptop workstation locked.")

        elif act == "screenshot":
            from core.tools.multimodal.image_tool import AnalyzeImageTool
            tool = AnalyzeImageTool()
            return await tool.execute(cancellation_token, query="Describe what is on my screen concisely.", image_path="screen")

        else:
            return ToolResult(success=False, error=f"Unknown laptop management action: '{act}'. Supported: launch, close, list_apps, system_stats, lock, screenshot.")
