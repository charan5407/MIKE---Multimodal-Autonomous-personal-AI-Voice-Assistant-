"""
Autonomous Project Builder and Coding Agent for MIKE.
Plans project architecture, writes complete file trees under ~/MikeProjects/,
initializes Git, runs and tests code, fixes errors in an automated loop (max N iterations),
and opens the finished project in VS Code.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.brain.base import ChatMessage
from core.brain.coding.prompts import CODE_FIXER_PROMPT, PROJECT_PLANNER_PROMPT
from core.brain.router import router as llm_router
from core.logger import logger
from core.tools.cancellation import CancellationToken


class ProjectBuilder:
    """End-to-end coding agent for autonomous software development."""

    def __init__(self, router=None, base_dir: Optional[Path] = None):
        self.router = router or llm_router
        self.projects_root = base_dir or (Path.home() / "MikeProjects")
        self.projects_root.mkdir(parents=True, exist_ok=True)

    def _clean_json(self, raw_text: str) -> Dict[str, Any]:
        """Extracts and parses JSON object from LLM response text."""
        # Remove markdown code fences if present
        text = re.sub(r"^```(?:json)?", "", raw_text.strip(), flags=re.MULTILINE)
        text = re.sub(r"```$", "", text.strip(), flags=re.MULTILINE)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in LLM response:\n{raw_text[:300]}")
        return json.loads(match.group(0))

    def _init_git(self, project_dir: Path) -> bool:
        """Initializes a local git repository inside the project directory."""
        try:
            res = subprocess.run(
                ["git", "init"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=10,
                shell=True,
            )
            logger.info(f"Initialized git repository in {project_dir}: {res.stdout.strip()}")
            return res.returncode == 0
        except Exception as e:
            logger.warning(f"Could not initialize git in {project_dir}: {e}")
            return False

    def _open_in_vscode(self, project_dir: Path) -> bool:
        """Launches the project directory in VS Code."""
        try:
            # Try 'code <path>'
            subprocess.Popen(["code", str(project_dir)], shell=True)
            logger.info(f"Opened project in VS Code: {project_dir}")
            return True
        except Exception as e:
            logger.warning(f"Failed to open VS Code: {e}")
            return False

    async def create_project(
        self,
        project_description: str,
        max_iterations: int = 3,
        open_vscode: bool = True,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """
        Plans, builds, tests, fixes, and launches a complete software project.
        """
        if cancellation_token and cancellation_token.is_cancelled:
            return {"success": False, "error": "Operation cancelled by user."}

        logger.info(f"Starting autonomous project generation for: '{project_description}'")

        # ----------------------------------------------------------------------
        # Stage 1: ARCHITECTURAL PLANNING & CODE GENERATION
        # ----------------------------------------------------------------------
        plan_messages = [
            ChatMessage(role="system", content=PROJECT_PLANNER_PROMPT),
            ChatMessage(role="user", content=f"Create a complete working project for: {project_description}"),
        ]

        response = await self.router.generate(plan_messages, temperature=0.2)
        try:
            plan = self._clean_json(response.content)
        except Exception as e:
            logger.error(f"Failed to parse project plan JSON: {e}")
            return {"success": False, "error": f"Failed to parse project plan: {e}"}

        raw_name = plan.get("project_name", "mike_project")
        clean_name = re.sub(r"[^\w\-]", "_", raw_name).strip("_").lower() or "mike_project"
        project_dir = self.projects_root / clean_name
        project_dir.mkdir(parents=True, exist_ok=True)

        if cancellation_token and cancellation_token.is_cancelled:
            return {"success": False, "error": "Operation cancelled before writing files."}

        # ----------------------------------------------------------------------
        # Stage 2: WRITE FILES & INIT GIT
        # ----------------------------------------------------------------------
        files = plan.get("files", {})
        written_files = []

        for rel_path, content in files.items():
            file_path = project_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            written_files.append(rel_path)
            logger.info(f"Wrote project file: {rel_path} ({len(content)} bytes)")

        # Init Git
        self._init_git(project_dir)

        # ----------------------------------------------------------------------
        # Stage 3: DEPENDENCY INSTALLATION (OPTIONAL)
        # ----------------------------------------------------------------------
        install_cmd = plan.get("install_command")
        if install_cmd and isinstance(install_cmd, str) and install_cmd.strip():
            logger.info(f"Running install command: {install_cmd}")
            try:
                subprocess.run(
                    install_cmd,
                    cwd=str(project_dir),
                    shell=True,
                    capture_output=True,
                    timeout=60,
                )
            except Exception as e:
                logger.warning(f"Install command warning: {e}")

        # ----------------------------------------------------------------------
        # Stage 4: ITERATIVE TEST-AND-FIX LOOP
        # ----------------------------------------------------------------------
        test_cmd = plan.get("test_command")
        # Default test command: check python syntax on written .py files if not specified
        if not test_cmd or not str(test_cmd).strip():
            py_files = [f for f in written_files if f.endswith(".py")]
            if py_files:
                test_cmd = f"python -m py_compile {' '.join(py_files)}"

        tests_passed = False
        iteration = 0
        fix_history = []

        while iteration < max_iterations:
            if cancellation_token and cancellation_token.is_cancelled:
                return {"success": False, "error": "Operation cancelled during test loop."}

            iteration += 1
            if not test_cmd:
                tests_passed = True
                break

            logger.info(f"[Test-and-Fix Loop {iteration}/{max_iterations}] Running: {test_cmd}")
            try:
                test_proc = subprocess.run(
                    test_cmd,
                    cwd=str(project_dir),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if test_proc.returncode == 0:
                    logger.info(f"Tests passed successfully on iteration {iteration}!")
                    tests_passed = True
                    break

                # Tests failed: gather error output and trigger fixer
                error_output = (test_proc.stderr or "") + "\n" + (test_proc.stdout or "")
                logger.warning(f"Test failure detected (code {test_proc.returncode}):\n{error_output[:400]}")

                # Read current files to provide context to fixer
                files_context = {}
                for f_rel in written_files:
                    try:
                        with open(project_dir / f_rel, "r", encoding="utf-8") as f:
                            files_context[f_rel] = f.read()
                    except Exception:
                        pass

                fixer_prompt = (
                    f"The project test command `{test_cmd}` failed with exit code {test_proc.returncode}.\n\n"
                    f"--- ERROR TRACEBACK ---\n{error_output}\n\n"
                    f"--- CURRENT FILES ---\n{json.dumps(files_context, indent=2)}\n\n"
                    "Provide the fixed replacement content for the failing file."
                )

                fix_messages = [
                    ChatMessage(role="system", content=CODE_FIXER_PROMPT),
                    ChatMessage(role="user", content=fixer_prompt),
                ]

                fix_resp = await self.router.generate(fix_messages, temperature=0.1)
                fix_data = self._clean_json(fix_resp.content)

                target_file = fix_data.get("failing_file")
                fixed_content = fix_data.get("fixed_content")

                if target_file and fixed_content:
                    target_path = project_dir / target_file
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write(fixed_content)
                    fix_history.append({
                        "iteration": iteration,
                        "file": target_file,
                        "summary": fix_data.get("fix_summary", "Bug fixed"),
                    })
                    logger.info(f"Applied automated fix to {target_file}: {fix_data.get('fix_summary')}")
                else:
                    break

            except subprocess.TimeoutExpired:
                logger.warning(f"Test command timed out on iteration {iteration}")
                break
            except Exception as e:
                logger.warning(f"Error during test execution: {e}")
                break

        # ----------------------------------------------------------------------
        # Stage 5: LAUNCH VS CODE
        # ----------------------------------------------------------------------
        opened_code = False
        if open_vscode:
            opened_code = self._open_in_vscode(project_dir)

        return {
            "success": True,
            "project_name": clean_name,
            "project_dir": str(project_dir),
            "description": plan.get("description", project_description),
            "files": written_files,
            "tests_passed": tests_passed,
            "test_command": test_cmd,
            "iterations_run": iteration,
            "fixes_applied": fix_history,
            "opened_vscode": opened_code,
        }


# Global project builder instance
project_builder = ProjectBuilder()

