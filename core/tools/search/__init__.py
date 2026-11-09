"""
Search Tools Package for MIKE.
Exports DuckDuckGo Web Search Tool.
"""

from core.tools.registry import tool_registry
from core.tools.search.web_search import WebSearchTool


def register_search_tools():
    """Registers web search tools into the central tool registry."""
    tools = [
        WebSearchTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)

