"""
MIKE Security Package: Permissions, Audit Logging, and Prompt Sanitization.
"""

from core.security.audit import AuditLogger, audit_logger
from core.security.permissions import ConfirmationRequest, PermissionManager, PermissionTier, permission_manager
from core.security.profile import ProfileManager, profile_manager
from core.security.sanitizer import PromptSanitizer, sanitizer


def register_profile_tools() -> None:
    """Registers personal profile querying tools in the central tool registry."""
    from core.security.profile_tool import QueryProfileTool
    from core.tools.registry import tool_registry

    tool_registry.register(QueryProfileTool())


__all__ = [
    "AuditLogger",
    "audit_logger",
    "ConfirmationRequest",
    "PermissionManager",
    "PermissionTier",
    "permission_manager",
    "ProfileManager",
    "profile_manager",
    "PromptSanitizer",
    "register_profile_tools",
    "sanitizer",
]

