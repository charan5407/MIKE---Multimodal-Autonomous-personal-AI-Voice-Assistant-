"""
Unit Tests for Phase 10: Coding Agent & Autonomous Project Builder.
Tests architectural planning, file tree generation, git init,
iterative test-and-fix loop (max N iterations), VS Code launch,
code file editor, and intent routing.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from core.brain.base import LLMResponse
from core.brain.coding.builder import ProjectBuilder
from core.brain.coding.tools import (
    CreateProjectTool,
    EditFileTool,
    ExplainCodeTool,
    InitGitRepoTool,
)
from core.brain.intent_router import IntentRouter
from core.tools.cancellation import root_cancellation_token


# ==============================================================================
# 1. Project Generation & File Tree Creation
# ==============================================================================

@pytest.mark.asyncio
async def test_project_builder_create_project(tmp_path):
    """Verifies end-to-end project generation, file creation, and git initialization."""
    mock_plan = {
        "project_name": "snake_game_pygame",
        "description": "Classic 2D snake arcade game",
        "files": {
            "main.py": "print('Snake Game Started')",
            "README.md": "# Snake Game\nRun python main.py",
            "test_game.py": "def test_init(): assert True",
        },
        "install_command": None,
        "test_command": "python -m py_compile main.py",
    }

    mock_router = MagicMock()
    mock_router.generate = AsyncMock(return_value=LLMResponse(
        content=json.dumps(mock_plan),
        provider="gemini",
        model="gemini-2.0-flash",
    ))

    builder = ProjectBuilder(router=mock_router, base_dir=tmp_path)

    with patch.object(builder, "_init_git", return_value=True) as mock_git, \
         patch.object(builder, "_open_in_vscode", return_value=True) as mock_code, \
         patch("subprocess.run") as mock_subproc:

        mock_test_proc = MagicMock()
        mock_test_proc.returncode = 0
        mock_subproc.return_value = mock_test_proc

        res = await builder.create_project(
            project_description="Snake game in Python",
            max_iterations=3,
            open_vscode=True,
            cancellation_token=root_cancellation_token,
        )

        assert res["success"] is True
        assert res["project_name"] == "snake_game_pygame"
        assert res["tests_passed"] is True
        mock_git.assert_called_once()
        mock_code.assert_called_once()

        # Check created files on disk
        proj_dir = tmp_path / "snake_game_pygame"
        assert (proj_dir / "main.py").exists()
        assert (proj_dir / "README.md").exists()
        assert (proj_dir / "test_game.py").exists()
        assert (proj_dir / "main.py").read_text(encoding="utf-8") == "print('Snake Game Started')"


# ==============================================================================
# 2. Iterative Test-and-Fix Loop
# ==============================================================================

@pytest.mark.asyncio
async def test_project_builder_test_and_fix_loop(tmp_path):
    """Verifies that test failures trigger the code fixer loop and update the failing file."""
    mock_plan = {
        "project_name": "calculator_cli",
        "description": "Simple CLI calculator",
        "files": {
            "calc.py": "def add(a, b): return a - b  # BUG: subtraction instead of addition",
        },
        "install_command": None,
        "test_command": "python test_calc.py",
    }

    mock_fix = {
        "failing_file": "calc.py",
        "fix_summary": "Fixed addition operator",
        "fixed_content": "def add(a, b): return a + b",
    }

    mock_router = MagicMock()
    # First call: project plan. Second call: code fixer
    mock_router.generate = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps(mock_plan), provider="gemini", model="gemini-2.0-flash"),
        LLMResponse(content=json.dumps(mock_fix), provider="gemini", model="gemini-2.0-flash"),
    ])

    builder = ProjectBuilder(router=mock_router, base_dir=tmp_path)

    with patch.object(builder, "_init_git", return_value=True), \
         patch.object(builder, "_open_in_vscode", return_value=True), \
         patch("subprocess.run") as mock_subproc:

        # First run fails (returncode 1), second run passes (returncode 0)
        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "AssertionError: 2 + 2 != 0"
        fail_proc.stdout = ""

        pass_proc = MagicMock()
        pass_proc.returncode = 0
        pass_proc.stderr = ""
        pass_proc.stdout = "OK"

        mock_subproc.side_effect = [fail_proc, pass_proc]

        res = await builder.create_project(
            project_description="Calculator with tests",
            max_iterations=3,
            open_vscode=False,
            cancellation_token=root_cancellation_token,
        )

        assert res["success"] is True
        assert res["tests_passed"] is True
        assert res["iterations_run"] == 2
        assert len(res["fixes_applied"]) == 1
        assert res["fixes_applied"][0]["file"] == "calc.py"

        # Verify file content was updated by fixer
        fixed_file = tmp_path / "calculator_cli" / "calc.py"
        assert fixed_file.read_text(encoding="utf-8") == "def add(a, b): return a + b"


# ==============================================================================
# 3. Edit File Tool
# ==============================================================================

@pytest.mark.asyncio
async def test_edit_file_tool(tmp_path):
    """Verifies file editing via snippet replacement and full overwrite."""
    tool = EditFileTool()
    test_file = tmp_path / "sample.py"
    test_file.write_text("def hello():\n    print('old')\n", encoding="utf-8")

    # Snippet replacement
    res = await tool.execute(
        root_cancellation_token,
        file_path=str(test_file),
        target_snippet="print('old')",
        replacement="print('new')",
    )
    assert res.success is True
    assert "print('new')" in test_file.read_text(encoding="utf-8")

    # Full overwrite
    res = await tool.execute(
        root_cancellation_token,
        file_path=str(test_file),
        new_content="print('completely overwritten')",
    )
    assert res.success is True
    assert test_file.read_text(encoding="utf-8") == "print('completely overwritten')"


# ==============================================================================
# 4. Explain Code & Init Git Tools
# ==============================================================================

@pytest.mark.asyncio
async def test_explain_code_tool():
    """Verifies ExplainCodeTool queries LLM with source code."""
    tool = ExplainCodeTool()

    with patch("core.brain.coding.tools.llm_router.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = LLMResponse(
            content="🎯 HIGH-LEVEL PURPOSE: Implementation of QuickSort in Python.",
            provider="gemini",
            model="gemini-2.0-flash",
        )

        res = await tool.execute(root_cancellation_token, code="def quicksort(arr): return arr")
        assert res.success is True
        assert "QuickSort" in res.output


@pytest.mark.asyncio
async def test_init_git_repo_tool(tmp_path):
    """Verifies git init tool execution."""
    tool = InitGitRepoTool()

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="Initialized empty Git repository")

        res = await tool.execute(root_cancellation_token, repo_path=str(tmp_path))
        assert res.success is True
        assert "Initialized" in res.output


# ==============================================================================
# 5. Intent Router Fast Path Tests
# ==============================================================================

def test_intent_router_coding_fast_paths():
    """Verifies instant matching for project builder voice/text commands."""
    router = IntentRouter()

    match = router.match("Mike, create a snake game in Python")
    assert match is not None
    assert match.tool_name == "create_project"
    assert "snake game in Python" in match.parameters["project_description"]

    match = router.match("create project FastAPI authentication service")
    assert match is not None
    assert match.tool_name == "create_project"
    assert "FastAPI authentication service" in match.parameters["project_description"]

    match = router.match("build a simple weather cli")
    assert match is not None
    assert match.tool_name == "create_project"
    assert "simple weather cli" in match.parameters["project_description"]

