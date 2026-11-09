"""
MIKE Security Audit Logger.
Writes structured JSONL audit records for every executed tool and sensitive action.
Files stored in logs/audit.jsonl (strictly excluded from Git).
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.config import settings
from core.logger import logger
from core.security.permissions import PermissionTier


class AuditLogger:
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or (settings.logs_dir / "audit.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_action(
        self,
        tool_name: str,
        tier: PermissionTier,
        args: Dict[str, Any],
        status: str,  # 'started', 'success', 'failed', 'cancelled'
        latency_ms: float = 0.0,
        reversible: bool = False,
        error: Optional[str] = None,
    ):
        """Appends an immutable structured audit log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_name": tool_name,
            "tier": tier.value,
            "args": self._sanitize_dict(args),
            "status": status,
            "latency_ms": round(latency_ms, 2),
            "reversible": reversible,
            "user": settings.owner_name,
            "error": error,
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write to audit log: {e}")

    def _sanitize_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Redacts sensitive values like passwords, tokens, or private profile data."""
        sanitized = {}
        for k, v in d.items():
            k_lower = k.lower()
            if any(s in k_lower for s in ["password", "secret", "token", "key"]):
                sanitized[k] = "[REDACTED_SECRET]"
            elif any(p in k_lower for p in ["profile", "dob", "birth", "credentials"]):
                sanitized[k] = "[REDACTED_PRIVATE_DATA]"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            else:
                sanitized[k] = v
        return sanitized


# Global audit logger instance
audit_logger = AuditLogger()

