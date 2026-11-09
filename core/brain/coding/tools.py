"""
Agent Tools for Coding & Project Builder for MIKE.
Exposes autonomous project generation, code file editing, git repo initialization, and code review.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from core.brain.base import ChatMessage
from core.brain.coding.builder import project_builder
from core.brain.coding.prompts import EXPLAIN_CODE_PROMPT
from core.brain.router import router as llm_router
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


# ==============================================================================
# 1. Create Project Tool
# ==============================================================================

class CreateProjectArgs(BaseModel):
    project_description: str = Field(..., description="Description of the project to create (e.g. 'Snake game in pygame', 'FastAPI REST API with auth').")
    open_vscode: bool = Field(default=True, description="Whether to open the finished project in VS Code.")
    max_iterations: int = Field(default=3, description="Maximum test-and-fix iterations to resolve bugs.")


class CreateProjectTool(BaseTool):
    """Plans, generates, inits git, tests, fixes, and launches a complete project in VS Code."""

    name = "create_project"
    description = "Plans and builds a complete project under ~/MikeProjects/, writes all files, inits git, runs tests, fixes errors in a loop, and opens in VS Code."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = CreateProjectArgs
    timeout_sec = 120.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        project_description: str = "",
        open_vscode: bool = True,
        max_iterations: int = 3,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            res = await project_builder.create_project(
                project_description=project_description,
                max_iterations=max_iterations,
                open_vscode=open_vscode,
                cancellation_token=cancellation_token,
            )

            if not res.get("success"):
                return ToolResult(success=False, error=res.get("error", "Project build failed."))

            p_name = res["project_name"]
            p_dir = res["project_dir"]
            files = res["files"]
            test_status = "Tests Passed" if res.get("tests_passed") else "Tests Incomplete"
            fixes = len(res.get("fixes_applied", []))

            msg = (
                f"Project '{p_name}' successfully built at `{p_dir}`. "
                f"Generated {len(files)} file(s). Status: {test_status} ({fixes} fix(es) applied). "
                f"{'Opened in VS Code.' if res.get('opened_vscode') else ''}"
            )

            return ToolResult(
                success=True,
                output=msg,
                data=res,
            )

        except Exception as e:
            logger.error(f"Error in CreateProjectTool: {e}")
            return ToolResult(success=False, error=f"Project creation failed: {e}")


# ==============================================================================
# 2. Edit Code File Tool
# ==============================================================================

class EditFileArgs(BaseModel):
    file_path: str = Field(..., description="Path to the file to edit.")
    new_content: Optional[str] = Field(default=None, description="Full replacement content for the file.")
    target_snippet: Optional[str] = Field(default=None, description="Exact existing text snippet to replace.")
    replacement: Optional[str] = Field(default=None, description="Replacement snippet for target_snippet.")


class EditFileTool(BaseTool):
    """Edits or modifies source code files."""

    name = "edit_code_file"
    description = "Modifies existing source code files by full replacement or snippet substitution."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = EditFileArgs
    timeout_sec = 10.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        file_path: str = "",
        new_content: Optional[str] = None,
        target_snippet: Optional[str] = None,
        replacement: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        target = Path(file_path).expanduser().resolve()
        if not target.exists():
            return ToolResult(success=False, error=f"File not found: {file_path}")

        try:
            with open(target, "r", encoding="utf-8") as f:
                original = f.read()

            if new_content is not None:
                content_to_write = new_content
            elif target_snippet is not None and replacement is not None:
                if target_snippet not in original:
                    return ToolResult(success=False, error=f"Target snippet not found in {file_path}.")
                content_to_write = original.replace(target_snippet, replacement)
            else:
                return ToolResult(success=False, error="Must specify either new_content or target_snippet with replacement.")

            with open(target, "w", encoding="utf-8") as f:
                f.write(content_to_write)

            return ToolResult(
                success=True,
                output=f"Successfully updated {file_path} ({len(content_to_write)} bytes).",
                data={"file_path": str(target), "bytes": len(content_to_write)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to edit file: {e}")


# ==============================================================================
# 3. Explain Code Tool
# ==============================================================================

class ExplainCodeArgs(BaseModel):
    code: Optional[str] = Field(default=None, description="Source code text to explain.")
    file_path: Optional[str] = Field(default=None, description="Path to file to explain.")


class ExplainCodeTool(BaseTool):
    """Explains source code architecture, data flow, and complexity."""

    name = "explain_code"
    description = "Explains code purpose, architecture, execution flow, and algorithmic complexity."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ExplainCodeArgs
    timeout_sec = 25.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        code: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        content = code
        if not content and file_path:
            p = Path(file_path).expanduser().resolve()
            if not p.exists():
                return ToolResult(success=False, error=f"File not found: {file_path}")
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()

        if not content or not content.strip():
            return ToolResult(success=False, error="No code or file content provided to explain.")

        messages = [
            ChatMessage(role="system", content=EXPLAIN_CODE_PROMPT),
            ChatMessage(role="user", content=f"Source Code:\n\n```\n{content}\n```"),
        ]

        resp = await llm_router.generate(messages, temperature=0.2)
        return ToolResult(
            success=True,
            output=resp.content,
            data={"file_path": file_path},
        )


# ==============================================================================
# 4. Init Git Repo Tool
# ==============================================================================

class InitGitRepoArgs(BaseModel):
    repo_path: str = Field(..., description="Directory path to initialize as a Git repository.")


class InitGitRepoTool(BaseTool):
    """Initializes a new Git repository in a directory."""

    name = "init_git_repo"
    description = "Initializes a Git repository in the target directory."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = InitGitRepoArgs
    timeout_sec = 10.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        repo_path: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        target = Path(repo_path).expanduser().resolve()
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)

        try:
            res = subprocess.run(
                ["git", "init"],
                cwd=str(target),
                capture_output=True,
                text=True,
                timeout=10,
                shell=True,
            )
            return ToolResult(
                success=res.returncode == 0,
                output=f"Git repository initialized at {target}: {res.stdout.strip()}",
                data={"repo_path": str(target)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to initialize git repository: {e}")

