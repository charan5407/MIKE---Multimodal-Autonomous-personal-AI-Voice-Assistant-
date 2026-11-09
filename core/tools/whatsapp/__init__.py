"""
WhatsApp Automation Tools Package for MIKE.
Exports Contact resolution and Voice-confirmed WhatsApp sender.
"""

from core.tools.registry import tool_registry
from core.tools.whatsapp.sender import ResolveContactTool, SendWhatsAppMessageTool


def register_whatsapp_tools():
    """Registers all WhatsApp tools into the central tool registry."""
    tools = [
        ResolveContactTool(),
        SendWhatsAppMessageTool(),
    ]
    for tool in tools:
        tool_registry.register(tool)

