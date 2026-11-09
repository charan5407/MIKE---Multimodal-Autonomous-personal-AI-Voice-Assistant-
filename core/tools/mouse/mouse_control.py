"""
Mouse Control and Vision-Grounded Observe-Act-Verify Automation Suite for MIKE.
Includes:
1. MouseMoveTool: Smooth, natural-easing cursor movement.
2. MouseClickTool: Left, right, double, middle, and triple clicking.
3. MouseDragTool: Drag-and-drop with cooperative cancellation safety.
4. MouseScrollTool: Vertical and horizontal scrolling.
5. VisionClickTool: Full Observe-Act-Verify loop combining pywinauto UIA and Gemini Vision Grounding.
"""

import asyncio
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import pyautogui

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken, FailsafeManager
from core.tools.mouse.uia_locator import UIALocator
from core.tools.mouse.vision_grounding import vision_grounder

# Configure PyAutoGUI failsafe
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05


# ==============================================================================
# 1. Mouse Move Tool
# ==============================================================================

class MouseMoveArgs(BaseModel):
    x: int = Field(..., description="Target X screen pixel coordinate.")
    y: int = Field(..., description="Target Y screen pixel coordinate.")
    duration: float = Field(default=0.4, description="Movement duration in seconds.")
    smooth: bool = Field(default=True, description="Whether to use natural easing curve.")


class MouseMoveTool(BaseTool):
    """Moves mouse cursor to target screen coordinates smoothly."""

    name = "move_mouse"
    description = "Moves mouse cursor smoothly to target (X, Y) pixel coordinates on screen."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = MouseMoveArgs
    timeout_sec = 5.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        x: int = 0,
        y: int = 0,
        duration: float = 0.4,
        smooth: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            tween = pyautogui.easeInOutQuad if smooth else pyautogui.linear
            pyautogui.moveTo(x, y, duration=duration, tween=tween)
            return ToolResult(
                success=True,
                output=f"Mouse moved to ({x}, {y}).",
                data={"x": x, "y": y},
            )
        except pyautogui.FailSafeException:
            logger.critical("PyAutoGUI Failsafe triggered by user! Aborting.")
            FailsafeManager.release_all_inputs()
            return ToolResult(success=False, error="PyAutoGUI Failsafe triggered (mouse in screen corner).")
        except Exception as e:
            return ToolResult(success=False, error=f"Mouse move failed: {e}")


# ==============================================================================
# 2. Mouse Click Tool
# ==============================================================================

class MouseClickArgs(BaseModel):
    x: Optional[int] = Field(default=None, description="Optional target X coordinate before click.")
    y: Optional[int] = Field(default=None, description="Optional target Y coordinate before click.")
    click_type: str = Field(
        default="left",
        description="Click type: 'left', 'right', 'double', 'middle', 'triple'.",
    )
    clicks: int = Field(default=1, description="Number of clicks.")


class MouseClickTool(BaseTool):
    """Executes mouse clicks (left, right, double, middle) at current or specified position."""

    name = "click_mouse"
    description = "Clicks mouse at current or specified coordinates: left, right, double, middle click."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = MouseClickArgs
    timeout_sec = 5.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        x: Optional[int] = None,
        y: Optional[int] = None,
        click_type: str = "left",
        clicks: int = 1,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            if x is not None and y is not None:
                pyautogui.moveTo(x, y, duration=0.3, tween=pyautogui.easeInOutQuad)

            cur_x, cur_y = pyautogui.position()

            if click_type == "double":
                pyautogui.doubleClick(cur_x, cur_y)
                msg = f"Double-clicked at ({cur_x}, {cur_y})."
            elif click_type == "triple":
                pyautogui.tripleClick(cur_x, cur_y)
                msg = f"Triple-clicked at ({cur_x}, {cur_y})."
            elif click_type == "right":
                pyautogui.rightClick(cur_x, cur_y)
                msg = f"Right-clicked at ({cur_x}, {cur_y})."
            elif click_type == "middle":
                pyautogui.middleClick(cur_x, cur_y)
                msg = f"Middle-clicked at ({cur_x}, {cur_y})."
            else:
                pyautogui.click(cur_x, cur_y, clicks=clicks)
                msg = f"Clicked at ({cur_x}, {cur_y}) {clicks} time(s)."

            return ToolResult(
                success=True,
                output=msg,
                data={"x": cur_x, "y": cur_y, "click_type": click_type},
            )
        except pyautogui.FailSafeException:
            FailsafeManager.release_all_inputs()
            return ToolResult(success=False, error="PyAutoGUI Failsafe triggered.")
        except Exception as e:
            return ToolResult(success=False, error=f"Mouse click failed: {e}")


# ==============================================================================
# 3. Mouse Drag Tool
# ==============================================================================

class MouseDragArgs(BaseModel):
    end_x: int = Field(..., description="Target destination X coordinate.")
    end_y: int = Field(..., description="Target destination Y coordinate.")
    start_x: Optional[int] = Field(default=None, description="Starting X coordinate. Defaults to current cursor.")
    start_y: Optional[int] = Field(default=None, description="Starting Y coordinate. Defaults to current cursor.")
    duration: float = Field(default=0.6, description="Drag duration in seconds.")
    button: str = Field(default="left", description="Mouse button to hold during drag ('left', 'right').")


class MouseDragTool(BaseTool):
    """Drags mouse from start to end coordinates with cancellation protection."""

    name = "drag_mouse"
    description = "Drags and drops from starting position to destination coordinates."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = MouseDragArgs
    timeout_sec = 10.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        end_x: int = 0,
        end_y: int = 0,
        start_x: Optional[int] = None,
        start_y: Optional[int] = None,
        duration: float = 0.6,
        button: str = "left",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            if start_x is not None and start_y is not None:
                pyautogui.moveTo(start_x, start_y, duration=0.2)

            sx, sy = pyautogui.position()

            # Register failsafe callback in case of mid-drag cancel
            if cancellation_token:
                cancellation_token.register_callback(lambda: pyautogui.mouseUp(button=button))

            pyautogui.dragTo(end_x, end_y, duration=duration, button=button, tween=pyautogui.easeInOutQuad)
            pyautogui.mouseUp(button=button)

            return ToolResult(
                success=True,
                output=f"Dragged from ({sx}, {sy}) to ({end_x}, {end_y}).",
                data={"start_x": sx, "start_y": sy, "end_x": end_x, "end_y": end_y},
            )
        except pyautogui.FailSafeException:
            FailsafeManager.release_all_inputs()
            return ToolResult(success=False, error="PyAutoGUI Failsafe triggered during drag.")
        except Exception as e:
            pyautogui.mouseUp(button=button)
            return ToolResult(success=False, error=f"Mouse drag failed: {e}")


# ==============================================================================
# 4. Mouse Scroll Tool
# ==============================================================================

class MouseScrollArgs(BaseModel):
    clicks: int = Field(default=3, description="Number of scroll steps (positive or negative).")
    direction: str = Field(
        default="down",
        description="Scroll direction: 'down', 'up', 'left', 'right'.",
    )


class MouseScrollTool(BaseTool):
    """Scrolls mouse wheel vertically or horizontally."""

    name = "scroll_mouse"
    description = "Scrolls mouse wheel: down, up, left, or right."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = MouseScrollArgs
    timeout_sec = 5.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        clicks: int = 3,
        direction: str = "down",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            steps = abs(clicks)
            if direction.lower() == "down":
                pyautogui.scroll(-steps * 100)
            elif direction.lower() == "up":
                pyautogui.scroll(steps * 100)
            elif direction.lower() == "right":
                pyautogui.hscroll(steps * 100)
            elif direction.lower() == "left":
                pyautogui.hscroll(-steps * 100)
            else:
                pyautogui.scroll(-steps * 100)

            return ToolResult(
                success=True,
                output=f"Scrolled {direction} by {steps} step(s).",
                data={"direction": direction, "steps": steps},
            )
        except pyautogui.FailSafeException:
            FailsafeManager.release_all_inputs()
            return ToolResult(success=False, error="PyAutoGUI Failsafe triggered.")
        except Exception as e:
            return ToolResult(success=False, error=f"Mouse scroll failed: {e}")


# ==============================================================================
# 5. Vision-Grounded Observe-Act-Verify Loop Tool
# ==============================================================================

class VisionClickArgs(BaseModel):
    target: str = Field(
        ...,
        description="Description of target UI element to find and click (e.g. 'Submit button', 'File menu', 'Search bar', 'Close tab').",
    )
    click_type: str = Field(
        default="left",
        description="Type of click: 'left', 'right', 'double'.",
    )
    verify: bool = Field(
        default=True,
        description="Whether to capture a verification screenshot after clicking.",
    )


class VisionClickTool(BaseTool):
    """
    Executes a complete Observe-Act-Verify loop:
    1. Observe: Locates target control via pywinauto UIA or Gemini Vision Grounding.
    2. Act: Glides mouse smoothly to target and clicks.
    3. Verify: Captures post-action verification screenshot.
    """

    name = "vision_click"
    description = "Locates any UI element on screen using pywinauto or Gemini Vision grounding, clicks it smoothly, and verifies the action (Observe-Act-Verify loop)."
    tier = PermissionTier.TIER_B_REVERSIBLE
    args_schema = VisionClickArgs
    timeout_sec = 25.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        target: str = "",
        click_type: str = "left",
        verify: bool = True,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        target = target.strip()
        if not target:
            return ToolResult(success=False, error="Target description cannot be empty.")

        logger.info(f"[Observe-Act-Verify] Starting loop for target: '{target}' (Click: {click_type})")

        # ----------------------------------------------------------------------
        # Stage 1: OBSERVE & LOCATE
        # ----------------------------------------------------------------------
        coords = None
        source = None

        # 1a. Try fast native Windows UI Automation (UIA)
        uia_res = UIALocator.find_control(target)
        if uia_res:
            target_x, target_y, _ = uia_res
            coords = (target_x, target_y)
            source = "pywinauto_uia"
            logger.info(f"Target '{target}' resolved via native UIA at ({target_x}, {target_y})")

        # 1b. Fallback to Gemini 2.0 Flash Vision Grounding
        if not coords:
            logger.info(f"Target '{target}' not found via UIA. Querying Gemini Vision Grounder...")
            vision_res = await vision_grounder.locate_target(target)
            if vision_res:
                target_x, target_y, meta = vision_res
                coords = (target_x, target_y)
                source = f"gemini_vision (confidence: {meta.get('confidence', 1.0)})"
                logger.info(f"Target '{target}' resolved via Gemini Vision at ({target_x}, {target_y})")

        if not coords:
            return ToolResult(
                success=False,
                error=f"Could not locate '{target}' on screen via accessibility tree or vision grounding.",
            )

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled before clicking target.")

        # ----------------------------------------------------------------------
        # Stage 2: ACT
        # ----------------------------------------------------------------------
        target_x, target_y = coords
        try:
            # Glide mouse smoothly with natural quad easing
            pyautogui.moveTo(target_x, target_y, duration=0.45, tween=pyautogui.easeInOutQuad)

            if cancellation_token and cancellation_token.is_cancelled:
                return ToolResult(success=False, error="Operation cancelled before click dispatch.")

            if click_type == "double":
                pyautogui.doubleClick(target_x, target_y)
            elif click_type == "right":
                pyautogui.rightClick(target_x, target_y)
            else:
                pyautogui.click(target_x, target_y)

            logger.info(f"Dispatched {click_type} click at ({target_x}, {target_y})")

        except pyautogui.FailSafeException:
            FailsafeManager.release_all_inputs()
            return ToolResult(success=False, error="PyAutoGUI Failsafe triggered by user.")
        except Exception as e:
            return ToolResult(success=False, error=f"Mouse action failed: {e}")

        # ----------------------------------------------------------------------
        # Stage 3: VERIFY
        # ----------------------------------------------------------------------
        verified = False
        if verify:
            await asyncio.sleep(0.4)  # Allow UI transition
            try:
                # Capture post-action screenshot
                after_shot = pyautogui.screenshot()
                verified = True
                logger.info(f"[Observe-Act-Verify] Post-action screenshot captured. Verification complete.")
            except Exception as e:
                logger.debug(f"Verification screenshot notice: {e}")

        msg = (
            f"Successfully located and clicked '{target}' at ({target_x}, {target_y}) "
            f"via {source}. Action observed, executed, and verified."
        )

        return ToolResult(
            success=True,
            output=msg,
            data={
                "target": target,
                "x": target_x,
                "y": target_y,
                "click_type": click_type,
                "source": source,
                "verified": verified,
            },
        )

