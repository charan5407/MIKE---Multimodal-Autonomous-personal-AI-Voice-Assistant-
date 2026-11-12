"""
System Automation Tools Package for MIKE.
Exports volume, brightness, lock, app control, clipboard/keyboard, and file management tools.
"""

from core.tools.registry import tool_registry
from core.tools.system.apps import CloseAppTool, ListAppsTool, OpenAppTool
from core.tools.system.brightness import GetBrightnessTool, SetBrightnessTool
from core.tools.system.clipboard_keyboard import (
    CopyTextTool,
    PasteTextTool,
    PressHotkeyTool,
    ScreenshotTool,
    TypeTextTool,
)
from core.tools.system.files import CopyFileTool, DeleteFileTool, MoveFileTool
from core.tools.system.lock import LockWorkstationTool
from core.tools.system.volume import GetVolumeTool, SetVolumeTool, ToggleMuteTool
from core.tools.system.laptop_manager import LaptopManagerTool


def register_system_tools():
    """Registers all system automation tools into the central tool registry."""
    tools = [
        # Laptop Manager
        LaptopManagerTool(),
        # Volume & Audio
        SetVolumeTool(),
        GetVolumeTool(),
        ToggleMuteTool(),
        # Display & Power
        SetBrightnessTool(),
        GetBrightnessTool(),
        LockWorkstationTool(),
        # Apps
        OpenAppTool(),
        CloseAppTool(),
        ListAppsTool(),
        # Keyboard & Clipboard
        CopyTextTool(),
        PasteTextTool(),
        TypeTextTool(),
        PressHotkeyTool(),
        ScreenshotTool(),
        # File operations
        MoveFileTool(),
        CopyFileTool(),
        DeleteFileTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)


# Auto-register on import
register_system_tools()

