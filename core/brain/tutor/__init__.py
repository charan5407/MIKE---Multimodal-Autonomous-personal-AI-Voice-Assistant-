"""
AIML Tutor and Debugger Package for MIKE.
Exports tutor mentors, debugger engines, and register_tutor_tools().
"""

from core.brain.tutor.debugger import CodeDebugger, code_debugger
from core.brain.tutor.tools import DebugCodeTool, ExplainConceptTool, GenerateQuizTool
from core.brain.tutor.tutor import AIMLTutor, aiml_tutor
from core.tools.registry import tool_registry


def register_tutor_tools():
    """Registers AIML tutor and code debugger tools into central registry."""
    tools = [
        ExplainConceptTool(),
        DebugCodeTool(),
        GenerateQuizTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)

