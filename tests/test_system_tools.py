"""
Unit and integration tests for MIKE Phase 6 System Control Tools.
Tests: Volume (pycaw), Brightness, Lock, Apps (psutil), Clipboard (pyperclip), Hotkeys, and File Operations.
"""

from pathlib import Path
import pytest

from core.security.permissions import PermissionTier
from core.tools.cancellation import CancellationToken
from core.tools.registry import tool_registry
import core.tools.system  # Auto-registers system tools
from core.tools.system.apps import CloseAppTool, ListAppsTool, OpenAppTool
from core.tools.system.brightness import GetBrightnessTool, SetBrightnessTool
from core.tools.system.clipboard_keyboard import (
    CopyTextTool,
    PasteTextTool,
    PressHotkeyTool,
    ScreenshotTool,
    TypeTextTool,
)
from core.tools.system.files import CopyFileTool, DeleteFileTool, MoveFileTool
from core.tools.system.lock import LockWorkstationTool
from core.tools.system.volume import GetVolumeTool, SetVolumeTool, ToggleMuteTool


@pytest.mark.asyncio
async def test_volume_tools_execution():
    get_tool = GetVolumeTool()
    set_tool = SetVolumeTool()
    mute_tool = ToggleMuteTool()
    token = CancellationToken()

    # Test reading current volume
    res_get = await get_tool.execute(token)
    assert res_get.success
    original_level = res_get.output["level"]
    assert 0 <= original_level <= 100

    # Test setting volume safely (e.g. set to original level or 50)
    res_set = await set_tool.execute(token, level=original_level)
    assert res_set.success

    # Test mute toggle
    res_mute = await mute_tool.execute(token)
    assert res_mute.success
    # Restore mute state
    await mute_tool.execute(token, mute=res_get.output["is_muted"])


@pytest.mark.asyncio
async def test_brightness_tools_execution():
    get_tool = GetBrightnessTool()
    token = CancellationToken()

    res_get = await get_tool.execute(token)
    assert res_get.success
    assert "brightness" in res_get.output.lower()


@pytest.mark.asyncio
async def test_clipboard_operations():
    copy_tool = CopyTextTool()
    paste_tool = PasteTextTool()
    token = CancellationToken()

    test_message = "MIKE Autonomous Assistant - Clipboard Test"
    res_copy = await copy_tool.execute(token, text=test_message)
    assert res_copy.success

    res_paste = await paste_tool.execute(token)
    assert res_paste.success
    assert res_paste.output["clipboard_text"] == test_message


@pytest.mark.asyncio
async def test_file_operations_lifecycle(tmp_path: Path):
    copy_tool = CopyFileTool()
    move_tool = MoveFileTool()
    delete_tool = DeleteFileTool()
    token = CancellationToken()

    # 1. Create source file
    src_file = tmp_path / "hello.txt"
    src_file.write_text("Hello Charan", encoding="utf-8")
    assert src_file.exists()

    # 2. Test CopyFileTool
    copy_dst = tmp_path / "hello_copy.txt"
    res_copy = await copy_tool.execute(token, source=str(src_file), destination=str(copy_dst))
    assert res_copy.success
    assert copy_dst.exists()
    assert copy_dst.read_text(encoding="utf-8") == "Hello Charan"

    # 3. Test MoveFileTool
    move_dst = tmp_path / "hello_moved.txt"
    res_move = await move_tool.execute(token, source=str(copy_dst), destination=str(move_dst))
    assert res_move.success
    assert move_dst.exists()
    assert not copy_dst.exists()

    # Test Rollback of MoveFileTool
    rollback_ok = await move_tool.rollback(res_move.rollback_data)
    assert rollback_ok is True
    assert copy_dst.exists()

    # 4. Test DeleteFileTool (Tier C - Safe Recycle Bin deletion)
    assert delete_tool.tier == PermissionTier.TIER_C_SENSITIVE
    res_del = await delete_tool.execute(token, path=str(src_file))
    assert res_del.success
    assert not src_file.exists()


@pytest.mark.asyncio
async def test_app_and_lock_schemas():
    lock_tool = LockWorkstationTool()
    open_tool = OpenAppTool()
    close_tool = CloseAppTool()
    list_tool = ListAppsTool()
    token = CancellationToken()

    # Verify lock tool definition
    assert lock_tool.name == "lock_workstation"

    # Verify listing applications
    res_list = await list_tool.execute(token)
    assert res_list.success
    assert "running_apps" in res_list.output
    assert isinstance(res_list.output["running_apps"], list)

    # Verify tool schemas in registry
    assert tool_registry.get("open_app") is not None
    assert tool_registry.get("set_volume") is not None
    assert tool_registry.get("delete_file") is not None
