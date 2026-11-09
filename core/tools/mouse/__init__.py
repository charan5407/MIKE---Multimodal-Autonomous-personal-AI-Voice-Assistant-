"""
Mouse Automation & Vision Grounding Package for MIKE.
Exports move, click, drag, scroll, and the Vision-grounded Observe-Act-Verify loop.
"""

from core.tools.mouse.mouse_control import (
    MouseClickTool,
    MouseDragTool,
    MouseMoveTool,
    MouseScrollTool,
    VisionClickTool,
)
from core.tools.mouse.uia_locator import UIALocator
from core.tools.mouse.vision_grounding import VisionGrounder, vision_grounder
from core.tools.registry import tool_registry


def register_mouse_tools():
    """Registers all mouse control and vision grounding tools into the central tool registry."""
    tools = [
        MouseMoveTool(),
        MouseClickTool(),
        MouseDragTool(),
        MouseScrollTool(),
        VisionClickTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)

