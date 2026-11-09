"""
Windows UI Automation Locator for MIKE.
Uses pywinauto (UIA backend) to detect named controls (buttons, inputs, menus)
and extract their physical screen bounding boxes and center coordinates.
Provides fast (<50ms), offline, zero-token UI grounding for native desktop controls.
"""

import sys
from typing import Dict, List, Optional, Tuple
from core.logger import logger

try:
    import pywinauto
    from pywinauto import Desktop
except ImportError:
    pywinauto = None
    Desktop = None


class UIALocator:
    """Locates desktop and window controls using Windows Accessibility / UI Automation."""

    @staticmethod
    def is_available() -> bool:
        return sys.platform == "win32" and pywinauto is not None

    @classmethod
    def find_control(
        cls,
        target_name: str,
        control_type: Optional[str] = None,
        max_depth: int = 4,
    ) -> Optional[Tuple[int, int, Dict[str, int]]]:
        """
        Searches desktop accessibility tree for a named control.
        Returns (center_x, center_y, {"left": ..., "top": ..., "right": ..., "bottom": ...})
        or None if not found.
        """
        if not cls.is_available():
            return None

        clean_target = target_name.strip().lower()
        if not clean_target:
            return None

        try:
            desktop = Desktop(backend="uia")
            # Enumerate top-level visible windows
            windows = desktop.windows(visible_only=True)
            if not windows:
                return None

            # Prioritize foreground window
            foreground_win = None
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                for w in windows:
                    if w.handle == hwnd:
                        foreground_win = w
                        break
            except Exception:
                foreground_win = windows[0] if windows else None

            candidate_windows = [foreground_win] if foreground_win else []
            for w in windows[:8]:  # inspect top 8 windows
                if w != foreground_win:
                    candidate_windows.append(w)

            for win in candidate_windows:
                if not win:
                    continue
                try:
                    # Search children
                    descendants = win.descendants(depth=max_depth)
                    for elem in descendants:
                        try:
                            elem_text = (elem.window_text() or "").strip().lower()
                            elem_type = (elem.element_info.control_type or "").lower()

                            # Check control type filter if specified
                            if control_type and control_type.lower() not in elem_type:
                                continue

                            # Check name match
                            if clean_target == elem_text or clean_target in elem_text:
                                rect = elem.rectangle()
                                if rect.width() > 0 and rect.height() > 0:
                                    cx = (rect.left + rect.right) // 2
                                    cy = (rect.top + rect.bottom) // 2
                                    logger.info(
                                        f"UIALocator found '{target_name}' at ({cx}, {cy}) in window '{win.window_text()}'"
                                    )
                                    return cx, cy, {
                                        "left": rect.left,
                                        "top": rect.top,
                                        "right": rect.right,
                                        "bottom": rect.bottom,
                                    }
                        except Exception:
                            continue
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"UIALocator search error: {e}")

        return None

