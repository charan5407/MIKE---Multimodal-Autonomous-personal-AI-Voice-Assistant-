"""
YouTube Integration for MIKE.
Provides fast video search & playback via yt-dlp and browser control.
Supports 'Mike, play <query> on YouTube', pause, next, and fullscreen controls.
"""

import urllib.parse
import webbrowser
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import pyautogui

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class PlayYouTubeArgs(BaseModel):
    query: str = Field(..., description="The song title, artist, or video topic to search and play on YouTube.")


class PlayYouTubeTool(BaseTool):
    """Searches YouTube using yt-dlp and opens top video in default browser."""

    name = "play_youtube"
    description = "Searches YouTube for a song, music video, or topic using yt-dlp and opens the top result in the default browser."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = PlayYouTubeArgs
    timeout_sec = 15.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        query: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        if not query or not query.strip():
            return ToolResult(success=False, error="Query cannot be empty.")

        query = query.strip()
        logger.info(f"Searching YouTube for: '{query}'")

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        title = query
        video_url = None

        try:
            import yt_dlp

            ydl_opts = {
                "format": "best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "extract_flat": True,
                "skip_download": True,
                "default_search": "ytsearch1",
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=False)

                if info and "entries" in info and len(info["entries"]) > 0:
                    entry = info["entries"][0]
                    title = entry.get("title", query)
                    vid_id = entry.get("id")
                    raw_url = entry.get("url")

                    if raw_url and raw_url.startswith("http"):
                        video_url = raw_url
                    elif vid_id:
                        video_url = f"https://www.youtube.com/watch?v={vid_id}"

        except Exception as e:
            logger.warning(f"yt-dlp search error: {e}. Falling back to YouTube web search URL.")

        # Fallback to direct search URL if yt-dlp didn't resolve a direct video URL
        if not video_url:
            encoded = urllib.parse.quote(query)
            video_url = f"https://www.youtube.com/results?search_query={encoded}"
            title = f"Search results for '{query}'"

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled before launching browser.")

        # Open in default browser
        try:
            webbrowser.open(video_url)
            logger.info(f"Launched YouTube URL in default browser: {video_url}")
            return ToolResult(
                success=True,
                output=f"Playing '{title}' on YouTube: {video_url}",
                data={"title": title, "url": video_url, "query": query},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to open browser: {e}")


class ControlYouTubeArgs(BaseModel):
    action: str = Field(
        default="play_pause",
        description="Playback control action: pause, resume, play_pause, next, fullscreen, mute, rewind, forward.",
    )


class ControlYouTubeTool(BaseTool):
    """Controls YouTube playback via browser shortcut keys."""

    name = "control_youtube"
    description = "Controls YouTube playback: pause/resume (k/space), next video (Shift+N), fullscreen toggle (f), mute toggle (m), or seek."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ControlYouTubeArgs
    timeout_sec = 5.0

    VALID_ACTIONS = ["pause", "resume", "play_pause", "next", "fullscreen", "mute", "rewind", "forward"]

    async def execute(
        self,
        cancellation_token: CancellationToken,
        action: str = "play_pause",
        **kwargs: Any,
    ) -> ToolResult:
        action = action.lower().strip()
        if action not in self.VALID_ACTIONS:
            return ToolResult(success=False, error=f"Invalid action '{action}'. Choose from: {self.VALID_ACTIONS}")

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            if action in ["pause", "resume", "play_pause"]:
                pyautogui.press("k")
                msg = "Toggled YouTube play/pause."
            elif action == "next":
                pyautogui.hotkey("shift", "n")
                msg = "Skipped to next YouTube video."
            elif action == "fullscreen":
                pyautogui.press("f")
                msg = "Toggled YouTube fullscreen."
            elif action == "mute":
                pyautogui.press("m")
                msg = "Toggled YouTube mute."
            elif action == "rewind":
                pyautogui.press("j")  # 10s rewind
                msg = "Rewound YouTube video 10 seconds."
            elif action == "forward":
                pyautogui.press("l")  # 10s forward
                msg = "Advanced YouTube video 10 seconds."
            else:
                pyautogui.press("k")
                msg = f"Executed YouTube control: {action}"

            return ToolResult(
                success=True,
                output=msg,
                data={"action": action},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to send keyboard shortcut: {e}")
