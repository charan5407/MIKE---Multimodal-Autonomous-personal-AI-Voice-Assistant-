"""
FastAPI Core Application & IPC Server for MIKE.
Exposes REST endpoints and WebSocket stream for Desktop UI (Tauri / Electron).
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.brain.router import router as llm_router
from core.config import settings
from core.logger import logger
from core.server.ws import ws_manager
from core.voice.audio_stream import AudioStreamManager
from core.voice.coordinator import AssistantState, voice_coordinator


class SettingsUpdateRequest(BaseModel):
    wake_word_enabled: Optional[bool] = None
    microphone_index: Optional[int] = None
    voice_speed: Optional[str] = None
    voice_pitch: Optional[str] = None
    primary_provider: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


# Background task for sending live RMS amplitude to UI for 3D HUD
rms_task: Optional[asyncio.Task] = None


async def rms_broadcast_loop():
    """Streams live microphone RMS amplitude at 30fps to WebSocket for the 3D HUD."""
    try:
        while True:
            # Only broadcast RMS if UI clients are connected
            if ws_manager.active_connections:
                rms = voice_coordinator.audio.current_rms
                state = voice_coordinator.state.value
                await ws_manager.broadcast("rms", {"rms": round(rms, 3), "state": state})
            await asyncio.sleep(0.033)  # ~30 Hz update rate
    except asyncio.CancelledError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: wire up coordinator callbacks to WebSocket
    voice_coordinator.on_state_change = lambda s: asyncio.create_task(
        ws_manager.broadcast("state_change", {"state": s.value})
    )
    voice_coordinator.on_transcript = lambda t, is_final: asyncio.create_task(
        ws_manager.broadcast("transcript", {"text": t, "is_final": is_final})
    )
    voice_coordinator.on_response_chunk = lambda c: asyncio.create_task(
        ws_manager.broadcast("response_chunk", {"chunk": c})
    )

    # Start audio capture & voice coordinator
    coordinator_task = asyncio.create_task(voice_coordinator.start())
    global rms_task
    rms_task = asyncio.create_task(rms_broadcast_loop())
    logger.info("FastAPI server started, voice coordinator and RMS loops running.")

    yield

    # Shutdown
    if rms_task:
        rms_task.cancel()
    voice_coordinator.stop()
    coordinator_task.cancel()
    logger.info("FastAPI server shut down cleanly.")


app = FastAPI(
    title="MIKE Core Server",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "app": settings.app_name,
        "owner": settings.owner_name,
        "version": settings.app_version,
    }


@app.get("/api/status")
async def get_status():
    provider_status = await llm_router.get_provider_status()
    return {
        "state": voice_coordinator.state.value,
        "wake_word_enabled": voice_coordinator.wake.is_enabled,
        "active_provider": settings.llm_primary_provider,
        "providers": provider_status,
        "rms": round(voice_coordinator.audio.current_rms, 3),
    }


@app.get("/api/audio/devices")
async def get_audio_devices():
    return {"devices": AudioStreamManager.list_input_devices()}


@app.post("/api/action/stop")
async def action_stop():
    voice_coordinator.stop_all(reason="UI Stop Action")
    await ws_manager.broadcast("state_change", {"state": AssistantState.STOPPED.value})
    return {"status": "stopped"}


@app.post("/api/action/push-to-talk")
async def action_push_to_talk():
    voice_coordinator.trigger_push_to_talk()
    await ws_manager.broadcast("state_change", {"state": AssistantState.LISTENING.value})
    return {"status": "listening"}


@app.post("/api/action/chat")
async def action_chat(req: ChatRequest):
    """Processes typed search or chat input from the voice search bar."""
    if not req.message.strip():
        return {"error": "Empty message"}

    # Broadcast user query
    await ws_manager.broadcast("transcript", {"text": req.message, "is_final": True})
    await ws_manager.broadcast("state_change", {"state": AssistantState.THINKING.value})

    # Forward to voice coordinator speech handler logic
    asyncio.create_task(
        voice_coordinator._handle_user_speech(None)  # or direct LLM query
    )
    return {"status": "processing", "query": req.message}


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    if req.wake_word_enabled is not None:
        voice_coordinator.wake.set_enabled(req.wake_word_enabled)

    if req.microphone_index is not None:
        voice_coordinator.audio.stop()
        voice_coordinator.audio.device_index = req.microphone_index
        voice_coordinator.audio.start()

    if req.voice_speed is not None:
        voice_coordinator.tts.rate = req.voice_speed

    if req.voice_pitch is not None:
        voice_coordinator.tts.pitch = req.voice_pitch

    if req.primary_provider is not None:
        settings.llm_primary_provider = req.primary_provider

    await ws_manager.broadcast("settings_updated", {
        "wake_word_enabled": voice_coordinator.wake.is_enabled,
        "voice_speed": voice_coordinator.tts.rate,
        "voice_pitch": voice_coordinator.tts.pitch,
        "primary_provider": settings.llm_primary_provider,
    })
    return {"status": "updated"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial status snapshot on connect
        await websocket.send_json({
            "event": "init_state",
            "data": {
                "state": voice_coordinator.state.value,
                "wake_word_enabled": voice_coordinator.wake.is_enabled,
                "voice_speed": voice_coordinator.tts.rate,
                "primary_provider": settings.llm_primary_provider,
            }
        })

        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                action = msg.get("action")
                if action == "stop":
                    voice_coordinator.stop_all(reason="WebSocket Stop Command")
                elif action == "push_to_talk":
                    voice_coordinator.trigger_push_to_talk()
                elif action == "set_wake_word":
                    voice_coordinator.wake.set_enabled(msg.get("enabled", True))
                elif action == "ping":
                    await websocket.send_json({"event": "pong", "data": {}})
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

