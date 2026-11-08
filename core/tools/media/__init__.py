"""
Media Automation Tools Package for MIKE.
Exports YouTube and Spotify/Media Player playback controllers.
"""

from core.tools.media.spotify import ControlMediaPlaybackTool, PlayMusicTool
from core.tools.media.youtube import ControlYouTubeTool, PlayYouTubeTool
from core.tools.registry import tool_registry


def register_media_tools():
    """Registers all media tools into the central tool registry."""
    tools = [
        PlayYouTubeTool(),
        ControlYouTubeTool(),
        PlayMusicTool(),
        ControlMediaPlaybackTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)
