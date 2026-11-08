"""
MIKE Cancellation Token & Emergency Failsafe Subsystem.
Instantly interrupts active tools, releases held keys/mouse clicks, and manages rollbacks.
"""

import threading
from typing import Callable, List, Optional
from core.logger import logger

try:
    import pyautogui
    # Configure pyautogui emergency failsafe: slam mouse to any screen corner to abort
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
except ImportError:
    pyautogui = None


class CancellationToken:
    """Thread-safe cooperative cancellation token passed into long-running tools."""

    def __init__(self):
        self._is_cancelled = threading.Event()
        self._cancel_reason: Optional[str] = None
        self._callbacks: List[Callable[[], None]] = []
        self._lock = threading.Lock()

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled.is_set()

    @property
    def cancel_reason(self) -> Optional[str]:
        return self._cancel_reason

    def cancel(self, reason: str = "Emergency Stop"):
        """Signals cancellation and invokes registered teardown handlers."""
        with self._lock:
            if self._is_cancelled.is_set():
                return
            self._cancel_reason = reason
            self._is_cancelled.set()
            logger.warning(f"CancellationToken triggered: {reason}")

            # Trigger teardown callbacks
            for cb in self._callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.debug(f"Error executing cancellation callback: {e}")

            # Emergency release of any held input devices
            FailsafeManager.release_all_inputs()

    def register_callback(self, cb: Callable[[], None]):
        """Registers a cleanup callback to be called immediately upon cancellation."""
        with self._lock:
            if self._is_cancelled.is_set():
                try:
                    cb()
                except Exception:
                    pass
            else:
                self._callbacks.append(cb)

    def raise_if_cancelled(self):
        """Raises InterruptedError if cancellation was requested."""
        if self._is_cancelled.is_set():
            raise InterruptedError(f"Operation cancelled: {self._cancel_reason or 'Emergency stop'}")

    def reset(self):
        """Resets token state for new tasks."""
        with self._lock:
            self._is_cancelled.clear()
            self._cancel_reason = None
            self._callbacks.clear()


class FailsafeManager:
    """System-level failsafe to release held keyboard keys and mouse buttons."""

    @staticmethod
    def release_all_inputs():
        """Releases any active mouse clicks or modifier keys that might be held down."""
        if pyautogui is not None:
            try:
                # Release mouse buttons
                pyautogui.mouseUp(button="left")
                pyautogui.mouseUp(button="right")
                pyautogui.mouseUp(button="middle")

                # Release common modifier keys
                for key in ["shift", "ctrl", "alt", "win"]:
                    pyautogui.keyUp(key)

                logger.info("Failsafe: All mouse buttons and modifier keys released.")
            except Exception as e:
                logger.debug(f"Failsafe input release exception: {e}")


# Global root cancellation token
root_cancellation_token = CancellationToken()
