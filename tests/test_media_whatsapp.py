"""
Unit Tests for Phase 7: Media & WhatsApp Integration.
Tests YouTube search/playback, media keys, contact resolution,
Tier C voice confirmation enforcement for WhatsApp, and Intent Router fast paths.
"""

from unittest.mock import MagicMock, patch
import pytest

from core.brain.intent_router import IntentRouter
from core.tools.cancellation import root_cancellation_token
from core.tools.media.spotify import (
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PLAY_PAUSE,
    VK_MEDIA_PREV_TRACK,
    VK_MEDIA_STOP,
    ControlMediaPlaybackTool,
    PlayMusicTool,
)
from core.tools.media.youtube import ControlYouTubeTool, PlayYouTubeTool
from core.tools.whatsapp.sender import (
    ResolveContactTool,
    SendWhatsAppMessageTool,
    load_contacts,
    resolve_contact_phone,
)


@pytest.mark.asyncio
async def test_youtube_playback_tool():
    """Verifies YouTube search extracts top video and opens browser."""
    tool = PlayYouTubeTool()

    mock_info = {
        "entries": [
            {
                "id": "test12345",
                "title": "Interstellar Soundtrack",
                "url": "https://www.youtube.com/watch?v=test12345",
            }
        ]
    }

    with patch("yt_dlp.YoutubeDL") as MockYDL, patch("webbrowser.open") as mock_open:
        instance = MockYDL.return_value.__enter__.return_value
        instance.extract_info.return_value = mock_info

        res = await tool.execute(root_cancellation_token, query="Interstellar soundtrack")

        assert res.success is True
        assert res.data["title"] == "Interstellar Soundtrack"
        assert "https://www.youtube.com/watch?v=test12345" in res.data["url"]
        mock_open.assert_called_once_with("https://www.youtube.com/watch?v=test12345")


@pytest.mark.asyncio
async def test_youtube_control_shortcuts():
    """Verifies YouTube browser playback shortcuts (pause, next, fullscreen)."""
    tool = ControlYouTubeTool()

    with patch("pyautogui.press") as mock_press, patch("pyautogui.hotkey") as mock_hotkey:
        # Pause
        res = await tool.execute(root_cancellation_token, action="pause")
        assert res.success is True
        mock_press.assert_called_with("k")

        # Next
        res = await tool.execute(root_cancellation_token, action="next")
        assert res.success is True
        mock_hotkey.assert_called_with("shift", "n")

        # Fullscreen
        res = await tool.execute(root_cancellation_token, action="fullscreen")
        assert res.success is True
        mock_press.assert_called_with("f")


@pytest.mark.asyncio
async def test_media_playback_control_keys():
    """Verifies global virtual media key dispatch for Spotify/VLC."""
    tool = ControlMediaPlaybackTool()

    with patch("core.tools.media.spotify._send_media_key") as mock_key:
        res = await tool.execute(root_cancellation_token, action="play_pause")
        assert res.success is True
        mock_key.assert_called_with(VK_MEDIA_PLAY_PAUSE)

        res = await tool.execute(root_cancellation_token, action="next")
        assert res.success is True
        mock_key.assert_called_with(VK_MEDIA_NEXT_TRACK)

        res = await tool.execute(root_cancellation_token, action="previous")
        assert res.success is True
        mock_key.assert_called_with(VK_MEDIA_PREV_TRACK)

        res = await tool.execute(root_cancellation_token, action="stop")
        assert res.success is True
        mock_key.assert_called_with(VK_MEDIA_STOP)


@pytest.mark.asyncio
async def test_play_music_tool():
    """Verifies music playback with query and empty query toggle."""
    tool = PlayMusicTool()

    # Empty query toggles play/pause
    with patch("core.tools.media.spotify._send_media_key") as mock_key:
        res = await tool.execute(root_cancellation_token, query=None)
        assert res.success is True
        assert res.data["action"] == "play_pause"
        mock_key.assert_called_with(VK_MEDIA_PLAY_PAUSE)

    # Search query opens Spotify search target
    with patch("webbrowser.open") as mock_open, patch("os.startfile", side_effect=Exception("No desktop app")):
        res = await tool.execute(root_cancellation_token, query="Starboy")
        assert res.success is True
        assert "spotify.com" in res.data["url"]
        mock_open.assert_called_once()


def test_contact_resolution():
    """Verifies contact resolution from contacts.example.json and raw phones."""
    # Example contacts: Dad, Mom, Rahul, Prof_Sharma
    name, phone = resolve_contact_phone("Dad")
    assert name == "Dad"
    assert phone == "+919876543210"

    name, phone = resolve_contact_phone("mom")
    assert name == "Mom"
    assert phone == "+919876543211"

    # Fuzzy match
    name, phone = resolve_contact_phone("prof sharma")
    assert name == "Prof_Sharma"
    assert phone == "+919876543213"

    # Raw phone number
    name, phone = resolve_contact_phone("+12345678901")
    assert phone == "+12345678901"

    # Unknown
    name, phone = resolve_contact_phone("NonExistentPerson")
    assert name is None
    assert phone is None


@pytest.mark.asyncio
async def test_whatsapp_strict_voice_confirmation():
    """
    STRICT REQUIREMENT: SendWhatsAppMessageTool MUST require explicit confirmation
    before dispatching, reading back recipient and message.
    """
    tool = SendWhatsAppMessageTool()

    # 1. Unconfirmed attempt -> MUST fail with requires_confirmation=True
    unconfirmed_res = await tool.execute(
        root_cancellation_token,
        recipient="Mom",
        message="I will reach home in 10 minutes",
        confirmed=False,
    )
    assert unconfirmed_res.success is False
    assert unconfirmed_res.requires_confirmation is True
    assert "Mom" in unconfirmed_res.confirmation_prompt
    assert "+919876543211" in unconfirmed_res.confirmation_prompt
    assert "I will reach home in 10 minutes" in unconfirmed_res.confirmation_prompt

    # 2. Confirmed attempt -> MUST open WhatsApp URI and succeed
    with patch("webbrowser.open") as mock_open, patch("os.startfile", side_effect=Exception("fallback to web")):
        confirmed_res = await tool.execute(
            root_cancellation_token,
            recipient="Mom",
            message="I will reach home in 10 minutes",
            confirmed=True,
        )
        assert confirmed_res.success is True
        assert confirmed_res.data["recipient"] == "Mom"
        assert confirmed_res.data["phone"] == "+919876543211"
        mock_open.assert_called_once()
        opened_url = mock_open.call_args[0][0]
        assert "919876543211" in opened_url
        assert "reach%20home" in opened_url


def test_intent_router_fast_paths():
    """Verifies instant (<10ms) intent matching across Phase 6 & 7 features."""
    router = IntentRouter()

    # YouTube Play
    match = router.match("Mike, play Bohemian Rhapsody on YouTube")
    assert match is not None
    assert match.tool_name == "play_youtube"
    assert match.parameters["query"] == "bohemian rhapsody"

    # YouTube Control
    match = router.match("pause youtube")
    assert match is not None
    assert match.tool_name == "control_youtube"
    assert match.parameters["action"] == "pause"

    # Spotify
    match = router.match("Mike, play Blinding Lights on Spotify")
    assert match is not None
    assert match.tool_name == "play_music"
    assert match.parameters["query"] == "blinding lights"

    # Global Media
    match = router.match("next song")
    assert match is not None
    assert match.tool_name == "control_media_playback"
    assert match.parameters["action"] == "next"

    # WhatsApp (Initiation -> Confirmation prompt)
    match = router.match("Mike, message Dad I got selected for the internship")
    assert match is not None
    assert match.tool_name == "send_whatsapp_message"
    assert match.requires_confirmation is True
    assert "Dad" in match.confirmation_prompt
    assert router.has_pending_confirmation is True

    # User voice confirmation: "Yes"
    confirm_match = router.match("yes")
    assert confirm_match is not None
    assert confirm_match.tool_name == "send_whatsapp_message"
    assert confirm_match.parameters["confirmed"] is True
    assert router.has_pending_confirmation is False

    # System Control
    match = router.match("Mike, lock the laptop")
    assert match is not None
    assert match.tool_name == "lock_workstation"

    match = router.match("set volume to 65")
    assert match is not None
    assert match.tool_name == "set_volume"
    assert match.parameters["level"] == 65

    match = router.match("open notepad")
    assert match is not None
    assert match.tool_name == "open_app"
    assert match.parameters["app_name"] == "notepad"
