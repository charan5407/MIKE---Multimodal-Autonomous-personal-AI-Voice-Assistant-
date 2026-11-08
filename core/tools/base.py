"""
BaseTool interface and execution result definitions for MIKE.
Integrates Pydantic JSON schemas, permission tiers, timeouts, and rollbacks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field

from core.brain.base import ToolDefinition
from core.security.permissions import PermissionTier
from core.tools.cancellation import CancellationToken


class ToolResult(BaseModel):
    success: bool
    output: Any = None
    error: Optional[str] = None
    reversible: bool = False
    rollback_data: Optional[Dict[str, Any]] = None


class BaseTool(ABC):
    name: str
    description: str
    tier: PermissionTier = PermissionTier.TIER_A_SAFE
    args_schema: Optional[Type[BaseModel]] = None
    timeout_sec: float = 30.0

    @abstractmethod
    async def execute(self, cancellation_token: CancellationToken, **kwargs) -> ToolResult:
        """Executes tool logic with cooperative cancellation support."""
        pass

    async def rollback(self, rollback_data: Dict[str, Any]) -> bool:
        """Optional rollback handler for reversible Tier B and Tier C actions."""
        return True

    def to_tool_definition(self) -> ToolDefinition:
        """Serializes tool into JSON Schema format compatible with Gemini, Groq, and Ollama."""
        parameters = {"type": "object", "properties": {}}
        if self.args_schema:
            schema = self.args_schema.model_json_schema()
            parameters = {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }

        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=parameters,
        )
