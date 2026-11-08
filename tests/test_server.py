"""
Unit and integration tests for MIKE FastAPI Core Server & WebSocket IPC.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from core.server.app import app
from core.voice.coordinator import AssistantState, voice_coordinator


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "online"
        assert data["app"] == "MIKE"
        assert data["owner"] == "Charan"


@pytest.mark.asyncio
async def test_api_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/status")
        assert res.status_code == 200
        data = res.json()
        assert "state" in data
        assert "wake_word_enabled" in data
        assert "providers" in data


@pytest.mark.asyncio
async def test_audio_devices_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/audio/devices")
        assert res.status_code == 200
        data = res.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)


@pytest.mark.asyncio
async def test_settings_update_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/settings",
            json={
                "wake_word_enabled": False,
                "voice_speed": "-6%",
            },
        )
        assert res.status_code == 200
        assert not voice_coordinator.wake.is_enabled
        assert voice_coordinator.tts.rate == "-6%"

        # Re-enable wake word
        await client.post("/api/settings", json={"wake_word_enabled": True})
        assert voice_coordinator.wake.is_enabled


@pytest.mark.asyncio
async def test_stop_and_push_to_talk_actions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test push-to-talk action
        ptt_res = await client.post("/api/action/push-to-talk")
        assert ptt_res.status_code == 200
        assert voice_coordinator.state == AssistantState.LISTENING

        # Test stop action
        stop_res = await client.post("/api/action/stop")
        assert stop_res.status_code == 200
        assert voice_coordinator.state in [AssistantState.STOPPED, AssistantState.IDLE]
