"""
Unit Tests for Phase 8: Mouse Control & Vision-Grounded Observe-Act-Verify Loop.
Tests smooth movement, clicking, dragging, scrolling, UIA accessibility location,
Gemini 2.0 Flash Vision Grounding, and end-to-end Observe-Act-Verify workflow.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import pyautogui
import pytest

from core.brain.intent_router import IntentRouter
from core.tools.cancellation import CancellationToken, root_cancellation_token
from core.tools.mouse.mouse_control import (
    MouseClickTool,
    MouseDragTool,
    MouseMoveTool,
    MouseScrollTool,
    VisionClickTool,
)
from core.tools.mouse.uia_locator import UIALocator
from core.tools.mouse.vision_grounding import VisionGrounder


@pytest.mark.asyncio
async def test_mouse_move_tool():
    """Verifies smooth mouse cursor movement and coordinate reporting."""
    tool = MouseMoveTool()

    with patch("pyautogui.moveTo") as mock_move:
        res = await tool.execute(root_cancellation_token, x=500, y=300, duration=0.4, smooth=True)

        assert res.success is True
        assert res.data["x"] == 500
        assert res.data["y"] == 300
        mock_move.assert_called_once_with(500, 300, duration=0.4, tween=pyautogui.easeInOutQuad)


@pytest.mark.asyncio
async def test_mouse_failsafe_handling():
    """Verifies that slamming mouse to screen corner triggers failsafe safely without crash."""
    tool = MouseMoveTool()

    with patch("pyautogui.moveTo", side_effect=pyautogui.FailSafeException()):
        res = await tool.execute(root_cancellation_token, x=0, y=0)
        assert res.success is False
        assert "Failsafe" in res.error


@pytest.mark.asyncio
async def test_mouse_click_types():
    """Verifies left, right, double, and middle click dispatches."""
    tool = MouseClickTool()

    with patch("pyautogui.position", return_value=(400, 400)), \
         patch("pyautogui.click") as mock_click, \
         patch("pyautogui.doubleClick") as mock_dclick, \
         patch("pyautogui.rightClick") as mock_rclick, \
         patch("pyautogui.middleClick") as mock_mclick:

        # Left click
        res = await tool.execute(root_cancellation_token, click_type="left")
        assert res.success is True
        mock_click.assert_called_once_with(400, 400, clicks=1)

        # Double click
        res = await tool.execute(root_cancellation_token, click_type="double")
        assert res.success is True
        mock_dclick.assert_called_once_with(400, 400)

        # Right click
        res = await tool.execute(root_cancellation_token, click_type="right")
        assert res.success is True
        mock_rclick.assert_called_once_with(400, 400)

        # Middle click
        res = await tool.execute(root_cancellation_token, click_type="middle")
        assert res.success is True
        mock_mclick.assert_called_once_with(400, 400)


@pytest.mark.asyncio
async def test_mouse_drag_tool():
    """Verifies smooth drag-and-drop interpolation and mouse button release."""
    tool = MouseDragTool()

    with patch("pyautogui.position", return_value=(100, 100)), \
         patch("pyautogui.dragTo") as mock_drag, \
         patch("pyautogui.mouseUp") as mock_up:

        res = await tool.execute(
            root_cancellation_token,
            start_x=100,
            start_y=100,
            end_x=500,
            end_y=600,
            duration=0.5,
            button="left",
        )

        assert res.success is True
        assert res.data["start_x"] == 100
        assert res.data["end_x"] == 500
        mock_drag.assert_called_once_with(500, 600, duration=0.5, button="left", tween=pyautogui.easeInOutQuad)
        mock_up.assert_called_once_with(button="left")


@pytest.mark.asyncio
async def test_mouse_scroll_tool():
    """Verifies vertical and horizontal mouse wheel scrolls."""
    tool = MouseScrollTool()

    with patch("pyautogui.scroll") as mock_scroll, patch("pyautogui.hscroll") as mock_hscroll:
        # Scroll down
        res = await tool.execute(root_cancellation_token, clicks=3, direction="down")
        assert res.success is True
        mock_scroll.assert_called_with(-300)

        # Scroll up
        res = await tool.execute(root_cancellation_token, clicks=5, direction="up")
        assert res.success is True
        mock_scroll.assert_called_with(500)

        # Horizontal scroll right
        res = await tool.execute(root_cancellation_token, clicks=2, direction="right")
        assert res.success is True
        mock_hscroll.assert_called_with(200)


@pytest.mark.asyncio
async def test_vision_grounder_coordinate_translation():
    """Verifies Gemini Vision normalized [0, 1000] coordinates map to exact physical screen pixels."""
    grounder = VisionGrounder(api_key="test_dummy_key")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"found": true, "x": 500, "y": 250, "confidence": 0.98, "description": "Save Button"}'
    mock_client.models.generate_content.return_value = mock_response
    grounder._client = mock_client

    # 1920x1080 mock screenshot
    mock_img = Image.new("RGB", (1920, 1080), color="white")

    pixel_x, pixel_y, meta = await grounder.locate_target("Save button", screenshot=mock_img)

    # Normalized 500/1000 -> 960px, 250/1000 -> 270px
    assert pixel_x == 960
    assert pixel_y == 270
    assert meta["confidence"] == 0.98
    assert meta["source"] == "gemini_vision"


@pytest.mark.asyncio
async def test_vision_click_observe_act_verify_loop_uia():
    """Verifies full Observe-Act-Verify loop via pywinauto native UIA accessibility."""
    tool = VisionClickTool()

    # Mock UIA finding control at (800, 200)
    with patch.object(UIALocator, "find_control", return_value=(800, 200, {"left": 750, "top": 180, "right": 850, "bottom": 220})), \
         patch("pyautogui.moveTo") as mock_move, \
         patch("pyautogui.click") as mock_click, \
         patch("pyautogui.screenshot", return_value=Image.new("RGB", (1920, 1080))):

        res = await tool.execute(root_cancellation_token, target="Save button", click_type="left", verify=True)

        assert res.success is True
        assert res.data["x"] == 800
        assert res.data["y"] == 200
        assert res.data["source"] == "pywinauto_uia"
        assert res.data["verified"] is True
        mock_move.assert_called_once_with(800, 200, duration=0.45, tween=pyautogui.easeInOutQuad)
        mock_click.assert_called_once_with(800, 200)


@pytest.mark.asyncio
async def test_vision_click_observe_act_verify_loop_vision_fallback():
    """Verifies Observe-Act-Verify loop when UIA is not applicable (e.g. web/canvas) falling back to Gemini Vision."""
    tool = VisionClickTool()

    # UIA returns None, VisionGrounder resolves to (450, 650)
    with patch.object(UIALocator, "find_control", return_value=None), \
         patch("core.tools.mouse.mouse_control.vision_grounder.locate_target", new_callable=AsyncMock) as mock_vision, \
         patch("pyautogui.moveTo") as mock_move, \
         patch("pyautogui.doubleClick") as mock_dclick, \
         patch("pyautogui.screenshot", return_value=Image.new("RGB", (1920, 1080))):

        mock_vision.return_value = (450, 650, {"confidence": 0.95})

        res = await tool.execute(root_cancellation_token, target="Submit invoice button", click_type="double", verify=True)

        assert res.success is True
        assert res.data["x"] == 450
        assert res.data["y"] == 650
        assert "gemini_vision" in res.data["source"]
        assert res.data["click_type"] == "double"
        assert res.data["verified"] is True
        mock_move.assert_called_once_with(450, 650, duration=0.45, tween=pyautogui.easeInOutQuad)
        mock_dclick.assert_called_once_with(450, 650)


def test_intent_router_mouse_fast_paths():
    """Verifies instant intent matching for mouse actions and scrolling."""
    router = IntentRouter()

    # Scroll
    match = router.match("scroll down")
    assert match is not None
    assert match.tool_name == "scroll_mouse"
    assert match.parameters["direction"] == "down"

    match = router.match("Mike, scroll up")
    assert match is not None
    assert match.tool_name == "scroll_mouse"
    assert match.parameters["direction"] == "up"

    # Vision Click
    match = router.match("click Submit button")
    assert match is not None
    assert match.tool_name == "vision_click"
    assert match.parameters["target"] == "Submit button"
    assert match.parameters["click_type"] == "left"

    match = router.match("Mike, double click project folder")
    assert match is not None
    assert match.tool_name == "vision_click"
    assert match.parameters["target"] == "project folder"
    assert match.parameters["click_type"] == "double"

    match = router.match("right click image")
    assert match is not None
    assert match.tool_name == "vision_click"
    assert match.parameters["target"] == "image"
    assert match.parameters["click_type"] == "right"

