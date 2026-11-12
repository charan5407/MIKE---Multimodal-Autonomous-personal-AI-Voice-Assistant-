"""
Coding Agent and Project Builder Package for MIKE.
Exports ProjectBuilder and register_coding_tools().
"""

from core.brain.coding.builder import ProjectBuilder, project_builder
from core.brain.coding.tools import (
    CreateProjectTool,
    EditFileTool,
    ExecuteCodeTool,
    ExplainCodeTool,
    InitGitRepoTool,
)
from core.tools.registry import tool_registry


def register_coding_tools():
    """Registers all autonomous coding and project builder tools into central registry."""
    tools = [
        CreateProjectTool(),
        EditFileTool(),
        ExecuteCodeTool(),
        ExplainCodeTool(),
        InitGitRepoTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)

