"""
Memory Tools (Features 7 & 14).
Provides RememberTool, RecallMemoryTool, and ForgetLastTool for persistent agentic learning.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field

from core.memory.long_term import long_term_memory
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class RememberInput(BaseModel):
    fact: str = Field(..., description="The fact, preference, or instruction to remember.")
    category: Optional[str] = Field(
        default="preference",
        description="Category of memory: 'preference', 'fact', 'rule', or 'general'.",
    )


class RememberTool(BaseTool):
    """Commits a user preference or fact to long-term memory."""

    name: str = "remember_fact"
    description: str = "Stores a personal preference, fact, or instruction into long-term memory."
    tier: PermissionTier = PermissionTier.TIER_A_SAFE
    args_schema: Type[BaseModel] = RememberInput

    async def execute(
        self,
        cancellation_token: CancellationToken,
        fact: str,
        category: str = "preference",
        **kwargs,
    ) -> ToolResult:
        if cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Remember action cancelled.")

        memory_id = long_term_memory.store(fact, category)
        if memory_id <= 0:
            return ToolResult(success=False, error="Could not save to memory.")

        return ToolResult(
            success=True,
            output="I've committed that to memory, Charan.",
            data={"memory_id": memory_id, "fact": fact},
        )


class RecallMemoryInput(BaseModel):
    query: str = Field(..., description="What to search or recall from memory.")


class RecallMemoryTool(BaseTool):
    """Searches long-term memory for previously learned facts or preferences."""

    name: str = "recall_memory"
    description: str = "Searches long-term persistent memory for previously stored facts or preferences."
    tier: PermissionTier = PermissionTier.TIER_A_SAFE
    args_schema: Type[BaseModel] = RecallMemoryInput

    async def execute(
        self,
        cancellation_token: CancellationToken,
        query: str,
        **kwargs,
    ) -> ToolResult:
        if cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Memory recall cancelled.")

        memories = long_term_memory.recall(query, limit=3)
        if not memories:
            return ToolResult(
                success=True,
                output=f"I don't have any saved memories matching '{query}', Charan.",
                data={"matches": []},
            )

        # Build natural voice-friendly response
        if len(memories) == 1:
            fact = memories[0]["content"]
            response_text = f"You previously told me: {fact}."
        else:
            facts = [m["content"] for m in memories]
            combined = "; ".join(facts)
            response_text = f"Here is what I remember: {combined}."

        return ToolResult(
            success=True,
            output=response_text,
            data={"matches": memories},
        )


class ForgetLastInput(BaseModel):
    topic: Optional[str] = Field(
        default=None,
        description="Optional topic or query to delete from memory. If omitted, deletes the latest memory.",
    )


class ForgetLastTool(BaseTool):
    """Deletes recent memories or topic matching 'Mike, forget that'."""

    name: str = "forget_last"
    description: str = "Deletes the most recently added memory entry or matches for a topic (e.g. 'Mike, forget that')."
    tier: PermissionTier = PermissionTier.TIER_B_REVERSIBLE
    reversible: bool = True
    args_schema: Type[BaseModel] = ForgetLastInput

    async def execute(
        self,
        cancellation_token: CancellationToken,
        topic: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        if cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Forget action cancelled.")

        if topic and topic.strip():
            count = long_term_memory.forget_matching(topic.strip())
            if count > 0:
                return ToolResult(
                    success=True,
                    output=f"I have removed {count} memory items regarding '{topic}', Charan.",
                    reversible=False,
                )
            return ToolResult(
                success=True,
                output=f"I didn't find any memory items matching '{topic}' to forget.",
                reversible=False,
            )

        # Forget last
        deleted = long_term_memory.forget_last()
        if deleted:
            return ToolResult(
                success=True,
                output="I've removed that from my memory, Charan.",
                reversible=True,
                rollback_data={"content": deleted["content"], "category": deleted["category"]},
            )

        return ToolResult(
            success=True,
            output="There was no recent memory to forget, Charan.",
            reversible=False,
        )

    async def rollback(self, rollback_data: dict) -> bool:
        """Restores the forgotten memory if undone."""
        if not rollback_data:
            return False
        content = rollback_data.get("content")
        category = rollback_data.get("category", "general")
        if content:
            long_term_memory.store(content, category)
            return True
        return False
