"""
Agent Tools for AIML Tutor and Code Debugger.
Exposes concept explanations, exam mode, code traceback debugging, and interactive quizzes.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from core.brain.tutor.debugger import code_debugger
from core.brain.tutor.tutor import aiml_tutor
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class ExplainConceptArgs(BaseModel):
    concept: str = Field(..., description="The concept to explain (e.g. 'Backpropagation', 'Transformer Attention', 'PCA', 'Gradient Descent').")
    topic: Optional[str] = Field(default=None, description="Topic category (e.g. 'Deep Learning', 'Machine Learning', 'Linear Algebra', 'DSA').")
    level: str = Field(default="intermediate", description="Depth level: 'beginner', 'intermediate', 'advanced'.")
    mode: str = Field(default="standard", description="Explanation mode: 'standard' (analogy + code) or 'exam' (university 10-mark format).")


class ExplainConceptTool(BaseTool):
    """Explains AI, ML, Math, and CS concepts with pedagogical clarity or exam notes."""

    name = "explain_concept"
    description = "Explains AI/ML, Data Science, Math, or CS concepts with analogies, formulas, and code or university exam format."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ExplainConceptArgs
    timeout_sec = 25.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        concept: str = "",
        topic: Optional[str] = None,
        level: str = "intermediate",
        mode: str = "standard",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            explanation = await aiml_tutor.explain_concept(
                concept=concept,
                topic=topic,
                level=level,
                mode=mode,
            )
            return ToolResult(
                success=True,
                output=explanation,
                data={"concept": concept, "topic": topic, "level": level, "mode": mode},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to generate explanation: {e}")


class DebugCodeArgs(BaseModel):
    code: str = Field(..., description="The buggy or failing code snippet.")
    traceback: Optional[str] = Field(default=None, description="The execution traceback or error message.")
    language: str = Field(default="python", description="Programming language (e.g. 'python', 'cpp', 'sql').")
    file_path: Optional[str] = Field(default=None, description="Optional path to source file.")


class DebugCodeTool(BaseTool):
    """Analyzes code snippets and stack tracebacks to provide root-cause diagnostics and fixed code."""

    name = "debug_code"
    description = "Analyzes buggy code and error tracebacks, determines root cause, and provides corrected working code."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = DebugCodeArgs
    timeout_sec = 25.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        code: str = "",
        traceback: Optional[str] = None,
        language: str = "python",
        file_path: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            res = await code_debugger.debug_code(
                code=code,
                traceback=traceback,
                language=language,
                file_path=file_path,
            )
            return ToolResult(
                success=True,
                output=res["analysis"],
                data=res,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Debugging analysis failed: {e}")


class GenerateQuizArgs(BaseModel):
    topic: str = Field(default="Machine Learning", description="Quiz topic (e.g. 'Deep Learning', 'Transformers', 'NLP', 'DSA').")
    concept: Optional[str] = Field(default=None, description="Specific concept focus.")
    level: str = Field(default="intermediate", description="Difficulty: 'beginner', 'intermediate', 'advanced'.")


class GenerateQuizTool(BaseTool):
    """Generates an interactive technical quiz question with multiple-choice options."""

    name = "generate_quiz"
    description = "Generates interactive AIML technical quiz challenges for Charan to test understanding."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = GenerateQuizArgs
    timeout_sec = 20.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        topic: str = "Machine Learning",
        concept: Optional[str] = None,
        level: str = "intermediate",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            quiz = await aiml_tutor.generate_quiz(
                topic=topic,
                concept=concept,
                level=level,
            )
            return ToolResult(
                success=True,
                output=quiz,
                data={"topic": topic, "concept": concept, "level": level},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Quiz generation failed: {e}")

