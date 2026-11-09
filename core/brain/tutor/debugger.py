"""
Code Debugger and Traceback Analyzer for MIKE.
Analyzes syntax errors, runtime exceptions, tensor shape mismatches, and algorithmic bugs.
Provides root cause diagnostics, corrected code snippets, and optional file application.
"""

import re
from typing import Any, Dict, Optional
from core.brain.base import ChatMessage
from core.brain.router import router as llm_router
from core.brain.tutor.prompts import DEBUGGER_PROMPT
from core.logger import logger


class CodeDebugger:
    """Diagnoses code errors and tracebacks with automated fix generation."""

    def __init__(self, router=None):
        self.router = router or llm_router

    def extract_traceback_metadata(self, traceback_text: str) -> Dict[str, Any]:
        """Extracts file name, line number, and error type from Python traceback."""
        meta = {"error_type": None, "line_number": None, "file_name": None}
        if not traceback_text:
            return meta

        # Find line number
        line_match = re.findall(r'File "([^"]+)", line (\d+)', traceback_text)
        if line_match:
            meta["file_name"] = line_match[-1][0]
            meta["line_number"] = int(line_match[-1][1])

        # Find error type (last line usually ExceptionName: message)
        lines = [line.strip() for line in traceback_text.strip().splitlines() if line.strip()]
        if lines:
            last_line = lines[-1]
            if ":" in last_line:
                meta["error_type"] = last_line.split(":", 1)[0].strip()
            else:
                meta["error_type"] = last_line

        return meta

    async def debug_code(
        self,
        code: str,
        traceback: Optional[str] = None,
        language: str = "python",
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyzes code and error traceback, returning root cause, explanation, and fix.
        """
        tb_meta = self.extract_traceback_metadata(traceback or "")
        
        user_prompt = (
            f"Programming Language: {language}\n"
            f"File Path: {file_path or tb_meta.get('file_name') or 'inline_script'}\n\n"
            f"--- CODE ---\n{code}\n\n"
        )
        if traceback:
            user_prompt += f"--- TRACEBACK / ERROR ---\n{traceback}\n\n"

        user_prompt += (
            "Please provide:\n"
            "1. Root cause identification.\n"
            "2. Plain-English explanation of why this bug occurred.\n"
            "3. Complete corrected code snippet.\n"
            "4. Prevention best practices."
        )

        messages = [
            ChatMessage(role="system", content=DEBUGGER_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        logger.info(f"CodeDebugger analyzing error [{tb_meta.get('error_type') or 'code bug'}] in {language}")
        response = await self.router.generate(messages, temperature=0.1)

        return {
            "analysis": response.content,
            "error_type": tb_meta.get("error_type"),
            "line_number": tb_meta.get("line_number"),
            "file_name": tb_meta.get("file_name"),
            "original_code": code,
        }


# Global code debugger instance
code_debugger = CodeDebugger()

