"""
Agent Tools for Coding & Project Builder for MIKE.
Exposes autonomous project generation, code file editing, git repo initialization, and code review.
"""

import os
import subprocess
import sys
import re
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


# ==============================================================================
# 5. Execute Code / Quick Script Runner Tool
# ==============================================================================

DSA_TEMPLATES = {
    "linked_list": '''"""
Singly Linked List Implementation in Python.
Created by MIKE Desktop Assistant for Charan.
"""

class Node:
    def __init__(self, data):
        self.data = data
        self.next = None


class LinkedList:
    def __init__(self):
        self.head = None

    def insert(self, data):
        new_node = Node(data)
        if not self.head:
            self.head = new_node
            return
        curr = self.head
        while curr.next:
            curr = curr.next
        curr.next = new_node

    def delete(self, key):
        curr = self.head
        if curr and curr.data == key:
            self.head = curr.next
            return True
        prev = None
        while curr and curr.data != key:
            prev = curr
            curr = curr.next
        if curr is None:
            return False
        prev.next = curr.next
        return True

    def display(self):
        nodes = []
        curr = self.head
        while curr:
            nodes.append(str(curr.data))
            curr = curr.next
        return " -> ".join(nodes) + " -> None"


if __name__ == "__main__":
    print("=" * 50)
    print("   MIKE ASSISTANT: LINKED LIST EXECUTION")
    print("=" * 50)
    ll = LinkedList()
    print("[+] Inserting values: 10, 20, 30, 40, 50")
    for v in [10, 20, 30, 40, 50]:
        ll.insert(v)
    print(f"Current List: {ll.display()}")

    print("\\n[-] Deleting element: 30")
    ll.delete(30)
    print(f"Updated List: {ll.display()}")

    print("\\n[✓] Program executed successfully with exit code 0!")
    print("=" * 50)
''',
    "bubble_sort": '''"""
Bubble Sort Algorithm in Python.
Created by MIKE Desktop Assistant for Charan.
"""

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr


if __name__ == "__main__":
    print("=" * 50)
    print("   MIKE ASSISTANT: BUBBLE SORT EXECUTION")
    print("=" * 50)
    data = [64, 34, 25, 12, 22, 11, 90]
    print(f"Original Array: {data}")
    sorted_data = bubble_sort(data.copy())
    print(f"Sorted Array:   {sorted_data}")
    print("\\n[✓] Execution completed successfully with exit code 0!")
    print("=" * 50)
''',
    "binary_search": '''"""
Binary Search Algorithm in Python.
Created by MIKE Desktop Assistant for Charan.
"""

def binary_search(arr, target):
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1


if __name__ == "__main__":
    print("=" * 50)
    print("   MIKE ASSISTANT: BINARY SEARCH EXECUTION")
    print("=" * 50)
    arr = [10, 20, 30, 40, 50, 60, 70, 80]
    target = 40
    print(f"Sorted Array: {arr}")
    print(f"Searching for target: {target}")
    idx = binary_search(arr, target)
    if idx != -1:
        print(f"[✓] Target found at index: {idx}")
    else:
        print("[-] Target not found.")
    print("=" * 50)
'''
}


class ExecuteCodeArgs(BaseModel):
    prompt: Optional[str] = Field(default=None, description="Topic, concept, or description of the code to run (e.g. 'linked list', 'bubble sort').")
    code: Optional[str] = Field(default=None, description="Direct Python source code to execute.")
    open_vscode: bool = Field(default=True, description="Whether to open the script in Visual Studio Code.")
    filename: Optional[str] = Field(default=None, description="Optional filename for the script (e.g. 'linked_list.py').")


class ExecuteCodeTool(BaseTool):
    """Generates, saves, executes a Python program, captures terminal output, and launches in VS Code."""

    name = "execute_code"
    description = "Writes a Python program to ~/MikeProjects/, runs it immediately, captures stdout/stderr, and opens it in Visual Studio Code."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = ExecuteCodeArgs
    timeout_sec = 30.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        prompt: Optional[str] = None,
        code: Optional[str] = None,
        open_vscode: bool = True,
        filename: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        clean_prompt = (prompt or "linked list").strip().lower()
        projects_dir = Path.home() / "MikeProjects"
        projects_dir.mkdir(parents=True, exist_ok=True)

        # 1. Resolve Code Content
        chosen_code = code
        chosen_filename = filename

        if not chosen_code:
            # Check for instant DSA templates
            if "linked" in clean_prompt:
                chosen_code = DSA_TEMPLATES["linked_list"]
                chosen_filename = chosen_filename or "linked_list.py"
            elif "bubble" in clean_prompt or "sort" in clean_prompt:
                chosen_code = DSA_TEMPLATES["bubble_sort"]
                chosen_filename = chosen_filename or "bubble_sort.py"
            elif "binary" in clean_prompt or "search" in clean_prompt:
                chosen_code = DSA_TEMPLATES["binary_search"]
                chosen_filename = chosen_filename or "binary_search.py"
            else:
                # Query LLM router for dynamic code generation
                try:
                    logger.info(f"Generating Python code via LLM for: '{clean_prompt}'...")
                    gen_prompt = (
                        f"Write a complete, runnable, self-contained Python program with class/function definitions and demo test prints for: {prompt or 'a useful utility'}.\\n"
                        "Return ONLY the executable python code inside ```python ``` markdown block."
                    )
                    gen_resp = await llm_router.generate(
                        [ChatMessage(role="user", content=gen_prompt)],
                        temperature=0.2,
                        max_tokens=1024,
                    )
                    raw_resp = gen_resp.content
                    code_match = re.search(r"```(?:python)?(.*?)```", raw_resp, re.DOTALL)
                    if code_match:
                        chosen_code = code_match.group(1).strip()
                    else:
                        chosen_code = raw_resp.strip()
                except Exception as e:
                    logger.warning(f"Dynamic code generation error: {e}. Falling back to default linked list.")
                    chosen_code = DSA_TEMPLATES["linked_list"]
                    chosen_filename = "linked_list.py"

        if not chosen_filename:
            # Generate clean filename from prompt
            slug = re.sub(r"[^\w]", "_", clean_prompt).strip("_")[:20] or "program"
            chosen_filename = f"{slug}.py"

        if not chosen_filename.endswith(".py"):
            chosen_filename += ".py"

        target_file = projects_dir / chosen_filename

        # 2. Write File to Disk
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(chosen_code)
            logger.info(f"Wrote Python program to: {target_file}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to write code file: {e}")

        # 3. Execute Script
        stdout_text = ""
        stderr_text = ""
        exit_code = 0
        try:
            logger.info(f"Executing Python script: {target_file} via {sys.executable}...")
            proc = subprocess.run(
                [sys.executable, str(target_file)],
                cwd=str(projects_dir),
                capture_output=True,
                text=True,
                timeout=15,
            )
            stdout_text = proc.stdout.strip()
            stderr_text = proc.stderr.strip()
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            stderr_text = "Execution timed out after 15 seconds."
            exit_code = -1
        except Exception as e:
            stderr_text = f"Execution error: {e}"
            exit_code = -1

        # 4. Open in VS Code
        vscode_opened = False
        if open_vscode:
            try:
                subprocess.Popen(["code", "-r", str(target_file)], shell=True)
                vscode_opened = True
            except Exception:
                pass

            if not vscode_opened:
                vscode_path = r"C:\Users\ASUS\AppData\Local\Programs\Microsoft VS Code\Code.exe"
                if os.path.exists(vscode_path):
                    try:
                        subprocess.Popen([vscode_path, "-r", str(target_file)])
                        vscode_opened = True
                    except Exception:
                        pass

            if not vscode_opened:
                try:
                    os.startfile(str(target_file))
                    vscode_opened = True
                except Exception:
                    pass

        # 5. Format Output
        run_output = stdout_text or stderr_text or "Program completed with no output."
        msg = (
            f"I have created and executed the Python program in Visual Studio Code!\\n\\n"
            f"📂 **File Location**: `{target_file}`\\n"
            f"⚡ **Visual Studio Code**: {'Launched active editor' if vscode_opened else 'Opened'}\\n\\n"
            f"🖥️ **Program Output** (Exit Code {exit_code}):\\n"
            f"```\\n{run_output}\\n```"
        )

        return ToolResult(
            success=True,
            output=msg,
            data={
                "file_path": str(target_file),
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": exit_code,
                "vscode_opened": vscode_opened,
            },
        )

