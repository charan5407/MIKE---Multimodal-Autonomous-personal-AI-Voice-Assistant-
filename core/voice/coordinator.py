"""
Master Voice Pipeline Coordinator for MIKE.
Manages states: IDLE -> LISTENING -> THINKING -> SPEAKING -> STOPPED.
Coordinates Wake Word, VAD, STT (faster-whisper), LLM Router, and TTS (edge-tts / Piper) with Barge-In.
"""

import asyncio
import enum
import re
import threading
import time
from typing import Callable, List, Optional
import numpy as np

from core.brain.base import ChatMessage
from core.brain.intent_router import intent_router
from core.brain.router import router as llm_router
from core.logger import logger
from core.tools.cancellation import root_cancellation_token
from core.tools.registry import tool_registry
from core.voice.audio_stream import AudioStreamManager
from core.voice.stt import stt_engine
from core.voice.tts import tts_engine
from core.voice.vad import VoiceActivityDetector
from core.voice.wake import wake_detector


class AssistantState(str, enum.Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


STOP_PHRASES = ["stop", "mike stop", "hey mike stop", "cancel", "halt", "please stop"]


class VoiceCoordinator:
    def __init__(
        self,
        audio_stream: Optional[AudioStreamManager] = None,
        on_state_change: Optional[Callable[[AssistantState], None]] = None,
        on_transcript: Optional[Callable[[str, bool], None]] = None,
        on_response_chunk: Optional[Callable[[str], None]] = None,
    ):
        self.audio = audio_stream or AudioStreamManager()
        self.vad = VoiceActivityDetector()
        self.wake = wake_detector
        self.stt = stt_engine
        self.tts = tts_engine
        self.router = llm_router

        # UI Callbacks
        self.on_state_change = on_state_change
        self.on_transcript = on_transcript
        self.on_response_chunk = on_response_chunk

        self._state = AssistantState.IDLE
        self._is_running = False
        self._cancel_token = threading.Event()
        self._conversation_history: List[ChatMessage] = []
        self._loop_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> AssistantState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._is_running

    def set_state(self, new_state: AssistantState):
        """Transitions assistant state and notifies listeners (e.g. 3D HUD)."""
        if self._state != new_state:
            prev = self._state
            self._state = new_state
            logger.info(f"State transition: [{prev.value}] -> [{new_state.value}]")
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.debug(f"Error in on_state_change callback: {e}")

    def stop_all(self, reason: str = "User command"):
        """Emergency stop / cancellation: halts TTS, cancels current plan, resets state."""
        logger.info(f"Stop triggered: {reason}")
        self._cancel_token.set()
        self.tts.stop_playback()
        self.set_state(AssistantState.STOPPED)

        # Quick verbal confirmation if not already in stopped state
        asyncio.create_task(self._say_stopped())

    async def _say_stopped(self):
        try:
            await self.tts.speak("Stopped.")
        except Exception:
            pass
        finally:
            self._cancel_token.clear()
            self.set_state(AssistantState.IDLE)

    def trigger_push_to_talk(self):
        """Forces manual transition to LISTENING (e.g. via UI mic button or hotkey)."""
        if self._state == AssistantState.SPEAKING:
            self.tts.stop_playback()
        self.set_state(AssistantState.LISTENING)

    def _is_stop_command(self, text: str) -> bool:
        # Strip all punctuation and extra whitespace for reliable matching
        norm = re.sub(r"[^\w\s]", " ", text.lower())
        norm = re.sub(r"\s+", " ", norm).strip()
        return norm in STOP_PHRASES or norm.startswith("mike stop") or norm.startswith("hey mike stop")

    async def start(self):
        """Starts background voice processing loop."""
        if self._is_running:
            return

        self._is_running = True
        self.audio.start()
        self.set_state(AssistantState.IDLE)
        logger.info("MIKE Voice Pipeline Coordinator initialized and running.")

        try:
            while self._is_running:
                chunk = self.audio.read_chunk(timeout=0.05)
                if chunk is None:
                    await asyncio.sleep(0.005)
                    continue

                if self._state == AssistantState.IDLE:
                    # Monitor for wake word
                    if self.wake.process_chunk(chunk):
                        logger.info("Wake word detected! Switching to LISTENING.")
                        self.set_state(AssistantState.LISTENING)
                        self.vad.reset()

                elif self._state == AssistantState.LISTENING:
                    # User is actively speaking; record until VAD detects SPEECH_END
                    speech_frames = [chunk]
                    self.vad.reset()

                    while self._is_running and self._state == AssistantState.LISTENING:
                        c = self.audio.read_chunk(timeout=0.05)
                        if c is None:
                            await asyncio.sleep(0.005)
                            continue

                        speech_frames.append(c)
                        vad_res = self.vad.process_chunk(c)

                        if vad_res["event"] == "SPEECH_END":
                            logger.info(f"User finished speaking ({len(speech_frames)} frames recorded).")
                            break

                    if not self._is_running:
                        break

                    # Process captured speech
                    if len(speech_frames) > 5:
                        full_audio = np.concatenate(speech_frames)
                        await self._handle_user_speech(full_audio)
                    else:
                        self.set_state(AssistantState.IDLE)

                elif self._state == AssistantState.SPEAKING:
                    # Monitor for Barge-in (user speech interruption)
                    vad_res = self.vad.process_chunk(chunk)
                    if vad_res["prob"] >= 0.7:
                        logger.info("User speech detected while speaking! Triggering barge-in...")
                        self.tts.stop_playback()
                        self.set_state(AssistantState.LISTENING)

                await asyncio.sleep(0.001)

        except asyncio.CancelledError:
            logger.info("Voice coordinator loop cancelled.")
        except Exception as e:
            logger.error(f"Error in voice coordinator loop: {e}", exc_info=True)
            self.set_state(AssistantState.ERROR)
        finally:
            self.audio.stop()
            self._is_running = False

    async def _handle_user_speech(self, audio: Optional[np.ndarray] = None, direct_text: Optional[str] = None):
        """Processes voice speech or direct text, checks stop/intent commands, queries tools or LLM."""
        self.set_state(AssistantState.THINKING)

        text = ""
        if direct_text:
            text = direct_text.strip()
        elif audio is not None:
            # 1. Transcribe with faster-whisper (CUDA / CPU)
            text, latency = self.stt.transcribe(audio)
            logger.info(f"Transcribed ({latency:.0f}ms): '{text}'")

        if not text or not text.strip():
            self.set_state(AssistantState.IDLE)
            return

        if self.on_transcript:
            self.on_transcript(text, True)

        # 2. Check for stop command
        if self._is_stop_command(text):
            self.stop_all(reason=f"Voice command: '{text}'")
            return

        # 3. Fast-Path Intent Router Check (<10ms for media, system, WhatsApp, apps)
        intent = intent_router.match(text)
        if intent:
            logger.info(f"Fast-path intent matched: {intent.intent_name} -> {intent.tool_name}")
            self._conversation_history.append(ChatMessage(role="user", content=text))
            self.set_state(AssistantState.SPEAKING)

            if intent.intent_name == "cancel_action":
                response_text = "Action cancelled."
            elif intent.requires_confirmation:
                response_text = intent.confirmation_prompt or "Please confirm this action."
            else:
                # Direct tool execution
                tool_res = await tool_registry.execute(
                    intent.tool_name,
                    cancel_token=root_cancellation_token,
                    **intent.parameters,
                )
                response_text = tool_res.message if tool_res.success else f"I couldn't complete that: {tool_res.error}"

            if self.on_response_chunk:
                self.on_response_chunk(response_text)

            self._conversation_history.append(ChatMessage(role="assistant", content=response_text))
            try:
                await self.tts.speak(response_text)
            except Exception as e:
                logger.error(f"TTS error during intent response: {e}")
            finally:
                if not self._cancel_token.is_set():
                    self.set_state(AssistantState.IDLE)
            return

        # 4. Stream from Brain LLM Router (for general queries / complex planning)
        self._conversation_history.append(ChatMessage(role="user", content=text))
        self.set_state(AssistantState.SPEAKING)

        response_text = ""
        try:
            async for token in self.router.stream_generate(self._conversation_history):
                if self._cancel_token.is_set():
                    break
                response_text += token
                if self.on_response_chunk:
                    self.on_response_chunk(token)

            if response_text and not self._cancel_token.is_set():
                self._conversation_history.append(ChatMessage(role="assistant", content=response_text))
                # Speak response aloud with barge-in support
                await self.tts.speak(response_text)

        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            await self.tts.speak("I encountered an issue processing that. Could you repeat?")
        finally:
            if not self._cancel_token.is_set():
                self.set_state(AssistantState.IDLE)

    def stop(self):
        """Stops the voice coordinator and audio streams."""
        self._is_running = False
        self.audio.stop()
        self.tts.stop_playback()
        self.set_state(AssistantState.IDLE)


# Global coordinator instance
voice_coordinator = VoiceCoordinator()
