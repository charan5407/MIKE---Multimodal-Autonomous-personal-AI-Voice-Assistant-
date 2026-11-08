"""
File Management Tools for MIKE.
Supports move, rename, copy, and safe deletion to the Windows Recycle Bin via send2trash.
File deletion is strictly Tier C (Sensitive) and requires explicit confirmation from Charan.
"""

import os
import shutil
from pathlib import Path
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

try:
    import send2trash
except ImportError:
    send2trash = None


class MoveFileArgs(BaseModel):
    source: str = Field(description="Path to the file or directory to move or rename")
    destination: str = Field(description="Destination path")


class MoveFileTool(BaseTool):
    name = "move_file"
    description = "Moves or renames a file or directory from source to destination."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = MoveFileArgs

    async def execute(self, cancellation_token: CancellationToken, source: str, destination: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        src_path = Path(source).expanduser().resolve()
        dst_path = Path(destination).expanduser().resolve()

        if not src_path.exists():
            return ToolResult(success=False, error=f"Source path '{source}' does not exist.")

        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            logger.info(f"Moved file: {src_path} -> {dst_path}")
            return ToolResult(
                success=True,
                output=f"Successfully moved '{src_path.name}' to '{dst_path}'.",
                reversible=True,
                rollback_data={"source": str(dst_path), "destination": str(src_path)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error moving file: {e}")

    async def rollback(self, rollback_data: dict) -> bool:
        src = rollback_data.get("source")
        dst = rollback_data.get("destination")
        if src and dst and Path(src).exists():
            shutil.move(src, dst)
            return True
        return False


class CopyFileArgs(BaseModel):
    source: str = Field(description="Path to the source file to copy")
    destination: str = Field(description="Destination path")


class CopyFileTool(BaseTool):
    name = "copy_file"
    description = "Copies a file from source to destination."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = CopyFileArgs

    async def execute(self, cancellation_token: CancellationToken, source: str, destination: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        src_path = Path(source).expanduser().resolve()
        dst_path = Path(destination).expanduser().resolve()

        if not src_path.exists():
            return ToolResult(success=False, error=f"Source file '{source}' does not exist.")

        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_path), str(dst_path))
            logger.info(f"Copied file: {src_path} -> {dst_path}")
            return ToolResult(
                success=True,
                output=f"Successfully copied to '{dst_path}'.",
                reversible=True,
                rollback_data={"created_copy": str(dst_path)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Error copying file: {e}")


class DeleteFileArgs(BaseModel):
    path: str = Field(description="Path to the file to delete (safely moved to Recycle Bin)")


class DeleteFileTool(BaseTool):
    name = "delete_file"
    description = "Safely deletes a file by sending it to the Windows Recycle Bin (Tier C - Sensitive action)."
    tier = PermissionTier.TIER_C_SENSITIVE  # STRICTLY requires explicit confirmation!
    args_schema = DeleteFileArgs

    async def execute(self, cancellation_token: CancellationToken, path: str) -> ToolResult:
        cancellation_token.raise_if_cancelled()
        target_path = Path(path).expanduser().resolve()

        if not target_path.exists():
            return ToolResult(success=False, error=f"File '{path}' does not exist.")

        if send2trash is None:
            return ToolResult(success=False, error="send2trash library not available.")

        try:
            # Send to Windows Recycle Bin so user can restore if needed
            send2trash.send2trash(str(target_path))
            logger.warning(f"File sent to Recycle Bin: {target_path}")
            return ToolResult(
                success=True,
                output=f"File '{target_path.name}' was safely moved to the Recycle Bin.",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to delete file: {e}")

