"""
Multimodal Package for MIKE.
Registers text-to-image, vision QA, text-to-video, text-to-3d, and meeting summarization tools.
"""

from core.tools.registry import tool_registry
from core.tools.multimodal.image_tool import GenerateImageTool, AnalyzeImageTool, ShowLatestImageTool
from core.tools.multimodal.media_hub import GenerateVideoTool, Generate3DTool, SummarizeMeetingTool


def register_multimodal_tools():
    tool_registry.register(GenerateImageTool())
    tool_registry.register(AnalyzeImageTool())
    tool_registry.register(ShowLatestImageTool())
    tool_registry.register(GenerateVideoTool())
    tool_registry.register(Generate3DTool())
    tool_registry.register(SummarizeMeetingTool())

