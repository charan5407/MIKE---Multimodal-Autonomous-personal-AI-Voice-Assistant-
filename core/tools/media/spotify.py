"""
Spotify & Media Player Integration for MIKE.
Supports Spotify track/playlist search via spotipy (free developer API)
with automatic fallback to global Windows virtual media keys and local players (VLC, Windows Media Player).
Commands: play, pause, next, previous, volume, and play specific song/playlist.
"""

import ctypes
import os
import sys
import urllib.parse
import webbrowser
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import pyautogui

from core.config import settings
from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken

# Windows Virtual-Key Codes for Media
VK_MEDIA_NEXT_TRACK = 0xB0  # 176
VK_MEDIA_PREV_TRACK = 0xB1  # 177
VK_MEDIA_STOP = 0xB2        # 178
VK_MEDIA_PLAY_PAUSE = 0xB3   # 179
VK_VOLUME_DOWN = 0xAE       # 174
VK_VOLUME_UP = 0xAF         # 175
KEYEVENTF_KEYUP = 0x0002


def _send_media_key(vk_code: int):
    """Sends a hardware media key press & release via Windows API."""
    if sys.platform == "win32":
        ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
    else:
        # Cross-platform fallback using pyautogui
        key_map = {
            VK_MEDIA_PLAY_PAUSE: "playpause",
            VK_MEDIA_NEXT_TRACK: "nexttrack",
            VK_MEDIA_PREV_TRACK: "prevtrack",
            VK_VOLUME_UP: "volumeup",
            VK_VOLUME_DOWN: "volumedown",
        }
        key_name = key_map.get(vk_code)
        if key_name:
            pyautogui.press(key_name)


class PlayMusicArgs(BaseModel):
    query: Optional[str] = Field(
        default=None,
        description="Song title, artist name, or playlist to play (e.g. 'Starboy', 'lo-fi beats'). If omitted, toggles playback.",
    )
    player: str = Field(
        default="spotify",
        description="Target media player. Options: 'spotify', 'vlc', 'wmplayer', 'default'.",
    )


class PlayMusicTool(BaseTool):
    """Plays music on Spotify or local media players."""

    name = "play_music"
    description = "Play music on Spotify or local media player. Searches songs/playlists and launches playback or toggles media play."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = PlayMusicArgs
    timeout_sec = 10.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        query: Optional[str] = None,
        player: str = "spotify",
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        # If no query provided, simply toggle global play/pause
        if not query or not query.strip():
            _send_media_key(VK_MEDIA_PLAY_PAUSE)
            return ToolResult(
                success=True,
                output="Toggled media playback.",
                data={"action": "play_pause"},
            )

        query = query.strip()
        logger.info(f"Play music requested for query: '{query}', player: '{player}'")

        # 1. Check if Spotify API credentials exist in settings
        if settings.spotify_client_id and settings.spotify_client_secret:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials

                auth_manager = SpotifyClientCredentials(
                    client_id=settings.spotify_client_id,
                    client_secret=settings.spotify_client_secret,
                )
                sp = spotipy.Spotify(auth_manager=auth_manager)
                results = sp.search(q=query, type="track", limit=1)
                tracks = results.get("tracks", {}).get("items", [])

                if tracks:
                    track = tracks[0]
                    track_name = track["name"]
                    artist_name = track["artists"][0]["name"]
                    spotify_url = track["external_urls"]["spotify"]
                    spotify_uri = track["uri"]

                    logger.info(f"Found Spotify track: {track_name} by {artist_name} ({spotify_uri})")

                    # Launch Spotify Desktop URI if available, fallback to web
                    try:
                        if sys.platform == "win32":
                            os.startfile(spotify_uri)
                        else:
                            webbrowser.open(spotify_url)
                    except Exception:
                        webbrowser.open(spotify_url)

                    return ToolResult(
                        success=True,
                        output=f"Playing '{track_name}' by {artist_name} on Spotify: {spotify_url}",
                        data={
                            "track": track_name,
                            "artist": artist_name,
                            "url": spotify_url,
                            "uri": spotify_uri,
                        },
                    )
            except Exception as e:
                logger.warning(f"Spotify API search failed: {e}. Falling back to app/web search.")

        # 2. Zero-config / Free Fallback: Open Spotify Desktop search or Web Player
        search_query_encoded = urllib.parse.quote(query)
        web_url = f"https://open.spotify.com/search/{search_query_encoded}"
        desktop_uri = f"spotify:search:{search_query_encoded}"

        try:
            launched_target = "Spotify Web"
            if sys.platform == "win32":
                try:
                    os.startfile(desktop_uri)
                    launched_target = "Spotify Desktop App"
                except Exception:
                    webbrowser.open(web_url)
            else:
                webbrowser.open(web_url)

            # Send media play key after brief initiation
            _send_media_key(VK_MEDIA_PLAY_PAUSE)

            return ToolResult(
                success=True,
                output=f"Searching and playing '{query}' on {launched_target}: {web_url}",
                data={"query": query, "target": launched_target, "url": web_url},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to play music: {e}")


class ControlMediaPlaybackArgs(BaseModel):
    action: str = Field(
        default="play_pause",
        description="Media control action: play_pause, pause, play, next, previous, stop, volume_up, volume_down.",
    )


class ControlMediaPlaybackTool(BaseTool):
    """Controls global media playback via virtual media keys."""

    name = "control_media_playback"
    description = "Control media playback (Spotify, VLC, Windows Media Player, browsers): play_pause, pause, play, next, previous, stop, volume_up, volume_down."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = ControlMediaPlaybackArgs
    timeout_sec = 5.0

    VALID_ACTIONS = ["play_pause", "pause", "play", "next", "previous", "stop", "volume_up", "volume_down"]

    async def execute(
        self,
        cancellation_token: CancellationToken,
        action: str = "play_pause",
        **kwargs: Any,
    ) -> ToolResult:
        action = action.lower().strip()
        if action not in self.VALID_ACTIONS:
            return ToolResult(success=False, error=f"Invalid action '{action}'. Options: {self.VALID_ACTIONS}")

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        try:
            if action in ["play_pause", "pause", "play"]:
                _send_media_key(VK_MEDIA_PLAY_PAUSE)
                msg = "Toggled media play/pause."
            elif action == "next":
                _send_media_key(VK_MEDIA_NEXT_TRACK)
                msg = "Skipped to next track."
            elif action == "previous":
                _send_media_key(VK_MEDIA_PREV_TRACK)
                msg = "Returned to previous track."
            elif action == "stop":
                _send_media_key(VK_MEDIA_STOP)
                msg = "Stopped media playback."
            elif action == "volume_up":
                _send_media_key(VK_VOLUME_UP)
                msg = "Increased media volume."
            elif action == "volume_down":
                _send_media_key(VK_VOLUME_DOWN)
                msg = "Decreased media volume."
            else:
                _send_media_key(VK_MEDIA_PLAY_PAUSE)
                msg = f"Executed media control: {action}"

            return ToolResult(
                success=True,
                output=msg,
                data={"action": action},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to control media: {e}")
