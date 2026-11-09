"""
MIKE Long-Term and Short-Term Memory Package (Features 7 & 14).
"""

from core.memory.long_term import LongTermMemory, long_term_memory
from core.memory.short_term import ShortTermMemory, short_term_memory
from core.memory.tools import ForgetLastTool, RecallMemoryTool, RememberTool


def register_memory_tools() -> None:
    """Registers long-term memory tools in the central tool registry."""
    from core.tools.registry import tool_registry

    tool_registry.register(RememberTool())
    tool_registry.register(RecallMemoryTool())
    tool_registry.register(ForgetLastTool())


__all__ = [
    "LongTermMemory",
    "long_term_memory",
    "ShortTermMemory",
    "short_term_memory",
    "RememberTool",
    "RecallMemoryTool",
    "ForgetLastTool",
    "register_memory_tools",
]
