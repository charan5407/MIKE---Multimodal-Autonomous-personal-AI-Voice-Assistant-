"""
Tool Registry and Execution Dispatcher for MIKE.
Handles dynamic tool discovery, permission tier enforcement, audit logging, and WebSocket broadcasts.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import ValidationError

from core.brain.base import ToolDefinition
from core.logger import logger
from core.security.audit import audit_logger
from core.security.permissions import PermissionTier, permission_manager
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken, root_cancellation_token


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._activity_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register(self, tool: BaseTool):
        """Registers a tool instance into the catalog."""
        self._tools[tool.name.lower()] = tool
        logger.debug(f"Registered tool [{tool.name}] (Tier: {tool.tier.value})")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name.lower())

    def list_tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def get_all_definitions(self) -> List[ToolDefinition]:
        """Returns JSON schema definitions for all registered tools for the LLM."""
        return [tool.to_tool_definition() for tool in self._tools.values()]

    def on_activity(self, callback: Callable[[Dict[str, Any]], None]):
        self._activity_callbacks.append(callback)

    def set_activity_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Alias for on_activity to support external callback registration."""
        self._activity_callbacks.append(callback)

    async def _broadcast_activity(self, tool_name: str, tier: str, status: str, detail: str = ""):
        payload = {
            "tool": tool_name,
            "tier": tier,
            "status": status,
            "detail": detail,
            "timestamp": time.time(),
        }
        # Notify WebSocket UI clients
        try:
            from core.server.ws import ws_manager
            await ws_manager.broadcast("tool_activity", payload)
        except Exception:
            pass

        for cb in self._activity_callbacks:
            try:
                cb(payload)
            except Exception:
                pass

    async def execute_tool(
        self,
        name: str,
        args: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
        bypass_confirmation: bool = False,
    ) -> ToolResult:
        """
        Executes a registered tool through permission checks, timeouts, and audit trails.
        """
        token = cancellation_token or root_cancellation_token
        tool = self.get(name)

        if not tool:
            err_msg = f"Tool '{name}' is not registered."
            logger.error(err_msg)
            return ToolResult(success=False, error=err_msg)

        # 1. Permission Tier Enforcement (Tier C requires explicit confirmation)
        if tool.tier == PermissionTier.TIER_C_SENSITIVE and not bypass_confirmation:
            logger.info(f"Tool [{tool.name}] is Tier C (Sensitive). Requesting user confirmation...")
            confirmed = await permission_manager.request_confirmation(
                tool_name=tool.name,
                description=tool.description,
                args=args,
            )
            if not confirmed:
                logger.warning(f"Execution of [{tool.name}] cancelled: confirmation denied or timed out.")
                audit_logger.log_action(
                    tool_name=tool.name,
                    tier=tool.tier,
                    args=args,
                    status="denied",
                    error="User denied confirmation",
                )
                return ToolResult(success=False, error="Action cancelled: Confirmation denied by user.")

        # 2. Validate arguments with Pydantic schema if present
        if tool.args_schema:
            try:
                validated_args = tool.args_schema(**args).model_dump()
            except ValidationError as ve:
                err_msg = f"Invalid arguments for tool '{tool.name}': {ve}"
                logger.error(err_msg)
                return ToolResult(success=False, error=err_msg)
        else:
            validated_args = args

        # 3. Check for cancellation before launching
        if token.is_cancelled:
            logger.warning(f"Aborting [{tool.name}]: cancellation token already active.")
            return ToolResult(success=False, error="Operation cancelled prior to start.")

        # 4. Notify UI & start execution
        start_time = time.perf_counter()
        await self._broadcast_activity(tool.name, tool.tier.value, "started")

        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                tool.execute(cancellation_token=token, **validated_args),
                timeout=tool.timeout_sec,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Audit record
            status_str = "success" if result.success else "failed"
            audit_logger.log_action(
                tool_name=tool.name,
                tier=tool.tier,
                args=validated_args,
                status=status_str,
                latency_ms=latency_ms,
                reversible=result.reversible,
                error=result.error,
            )

            await self._broadcast_activity(
                tool.name,
                tool.tier.value,
                status_str,
                detail=str(result.output)[:80] if result.output else (result.error or ""),
            )
            return result

        except asyncio.TimeoutError:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Tool '{tool.name}' timed out after {tool.timeout_sec}s."
            logger.error(err_msg)
            audit_logger.log_action(
                tool_name=tool.name,
                tier=tool.tier,
                args=validated_args,
                status="timeout",
                latency_ms=latency_ms,
                error=err_msg,
            )
            await self._broadcast_activity(tool.name, tool.tier.value, "timeout", detail=err_msg)
            return ToolResult(success=False, error=err_msg)

        except InterruptedError as ie:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Tool '{tool.name}' interrupted by user: {ie}")
            audit_logger.log_action(
                tool_name=tool.name,
                tier=tool.tier,
                args=validated_args,
                status="cancelled",
                latency_ms=latency_ms,
                error=str(ie),
            )
            await self._broadcast_activity(tool.name, tool.tier.value, "cancelled", detail="Stopped by user")
            return ToolResult(success=False, error="Operation cancelled by user.")

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Unexpected error in '{tool.name}': {str(e)}"
            logger.error(err_msg, exc_info=True)
            audit_logger.log_action(
                tool_name=tool.name,
                tier=tool.tier,
                args=validated_args,
                status="failed",
                latency_ms=latency_ms,
                error=err_msg,
            )
            await self._broadcast_activity(tool.name, tool.tier.value, "failed", detail=err_msg)
            return ToolResult(success=False, error=err_msg)

    async def execute(
        self,
        name: str,
        cancel_token: Optional[CancellationToken] = None,
        cancellation_token: Optional[CancellationToken] = None,
        bypass_confirmation: bool = False,
        **kwargs,
    ) -> ToolResult:
        """Alias for execute_tool supporting keyword parameters and flexible cancellation naming."""
        token = cancel_token or cancellation_token or root_cancellation_token
        return await self.execute_tool(
            name=name,
            args=kwargs,
            cancellation_token=token,
            bypass_confirmation=bypass_confirmation,
        )


# Global tool registry
tool_registry = ToolRegistry()

