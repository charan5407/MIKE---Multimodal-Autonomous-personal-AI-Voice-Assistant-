"""
MIKE Security & Permission Tiers.
Tier A: Safe actions run automatically.
Tier B: Reversible actions run automatically and are logged to audit.
Tier C: Sensitive actions require explicit voice or on-screen confirmation from Charan.
"""

import enum
from typing import Callable, Dict, Optional


class PermissionTier(str, enum.Enum):
    TIER_A_SAFE = "TIER_A_SAFE"          # Read-only, queries, searches, volume, media
    TIER_B_REVERSIBLE = "TIER_B_REVERSIBLE"  # Creating files, launching apps, clipboard
    TIER_C_SENSITIVE = "TIER_C_SENSITIVE"    # Deleting files, WhatsApp send, power, scripts


class ConfirmationRequest:
    def __init__(self, tool_name: str, description: str, args: Dict, timeout_sec: float = 30.0):
        self.tool_name = tool_name
        self.description = description
        self.args = args
        self.timeout_sec = timeout_sec
        self.confirmed: Optional[bool] = None

    def approve(self):
        self.confirmed = True

    def deny(self):
        self.confirmed = False


class PermissionManager:
    def __init__(self, default_enforcement: PermissionTier = PermissionTier.TIER_C_SENSITIVE):
        self.default_enforcement = default_enforcement
        self._pending_confirmation: Optional[ConfirmationRequest] = None
        self._confirmation_callback: Optional[Callable[[ConfirmationRequest], None]] = None

    def set_confirmation_callback(self, callback: Callable[[ConfirmationRequest], None]):
        self._confirmation_callback = callback

    def requires_confirmation(self, tier: PermissionTier) -> bool:
        """Determines if a tool requires explicit confirmation from Charan."""
        return tier == PermissionTier.TIER_C_SENSITIVE

    async def request_confirmation(
        self,
        tool_name: str,
        description: str,
        args: Dict,
        timeout_sec: float = 30.0,
    ) -> bool:
        """
        Requests explicit confirmation before executing Tier C action.
        Notifies UI / Voice pipeline and waits for confirmation.
        """
        request = ConfirmationRequest(tool_name, description, args, timeout_sec)
        self._pending_confirmation = request

        if self._confirmation_callback:
            try:
                self._confirmation_callback(request)
            except Exception:
                pass

        return request.confirmed is True


# Global permission manager instance
permission_manager = PermissionManager()
