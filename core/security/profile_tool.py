"""
Query Profile Tool (Feature 8).
Privately retrieves personal details from encrypted store for Charan's ear only.
Strictly zero UI exposure, audio-only response.
"""

from typing import Optional, Type
from pydantic import BaseModel, Field

from core.security.permissions import PermissionTier
from core.security.profile import profile_manager
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class QueryProfileInput(BaseModel):
    query: str = Field(
        ...,
        description="The personal profile query or field, e.g. 'what is my age', 'who am i', 'what are my projects'.",
    )


class QueryProfileTool(BaseTool):
    """Answers Charan's profile queries strictly via audio with zero UI exposure."""

    name: str = "query_profile"
    description: str = (
        "Privately retrieves Charan's profile facts (name, age, DOB, education, projects, interests) "
        "from encrypted store for audio-only voice playback."
    )
    tier: PermissionTier = PermissionTier.TIER_A_SAFE
    args_schema: Type[BaseModel] = QueryProfileInput

    async def execute(
        self,
        cancellation_token: CancellationToken,
        query: str,
        **kwargs,
    ) -> ToolResult:
        if cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Profile query cancelled.")

        try:
            answer = profile_manager.get_audio_answer(query)
            return ToolResult(
                success=True,
                output=answer,
                data={"audio_only": True},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Could not retrieve profile info: {e}")
