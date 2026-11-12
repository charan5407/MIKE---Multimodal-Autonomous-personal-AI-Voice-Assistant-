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
        self._barge_in_counter = 0
        self._speaking_start_time = 0.0
        self._last_interaction_time = 0.0
        self._is_active_conversation = False

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
            if new_state == AssistantState.SPEAKING:
                self._speaking_start_time = time.time()
                self._barge_in_counter = 0
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

    async def _say_wake_acknowledgement(self):
        try:
            self.set_state(AssistantState.SPEAKING)
            ack = "Yes, I am here."
            if self.on_response_chunk:
                self.on_response_chunk(ack)
            await self.tts.speak(ack)
        except Exception:
            pass
        finally:
            self.audio.clear_queue()
            self.vad.reset()
            self.set_state(AssistantState.LISTENING)

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
                    # Monitor for openWakeWord triggers (hey jarvis, alexa, etc.)
                    wake_detected = self.wake.process_chunk(chunk)
                    vad_prob = self.vad.compute_speech_prob(chunk) if hasattr(self.vad, "compute_speech_prob") else 0.0

                    if wake_detected:
                        logger.info("Wake word detected via openWakeWord! Switching to LISTENING.")
                        self.vad.reset()
                        asyncio.create_task(self._say_wake_acknowledgement())
                    elif not self.wake.is_enabled and vad_prob >= 0.35:
                        # Direct speech mode when wake word is toggled off
                        self.set_state(AssistantState.LISTENING)
                        self.vad.reset()
                    elif self.wake.is_enabled and vad_prob >= 0.30:
                        # Buffer speech phrase to check for spoken "Mike" keyword or direct command
                        speech_frames = [chunk]
                        self.vad.reset()
                        while self._is_running and self._state == AssistantState.IDLE:
                            c = self.audio.read_chunk(timeout=0.05)
                            if c is None:
                                await asyncio.sleep(0.005)
                                continue
                            speech_frames.append(c)
                            vr = self.vad.process_chunk(c)
                            if vr["event"] == "SPEECH_END":
                                break
                            if len(speech_frames) > 100:  # ~3.2 seconds max
                                break

                        if len(speech_frames) > 6:
                            full_audio = np.concatenate(speech_frames)
                            text, latency = self.stt.transcribe(full_audio)
                            clean_t = text.lower().strip()
                            clean_norm = re.sub(r"[^\w\s]", " ", clean_t)
                            clean_norm = re.sub(r"\s+", " ", clean_norm).strip()

                            wake_keywords = [
                                "wake up mike", "hey mike", "mike", "mic", "hey mic",
                                "hello mike", "hi mike", "ok mike", "okay mike",
                                "hey jarvis", "jarvis", "alexa", "wake up"
                            ]

                            is_wake = any(
                                clean_norm == kw or clean_norm.startswith(f"{kw} ") or clean_norm.endswith(f" {kw}")
                                for kw in wake_keywords
                            )

                            if is_wake:
                                logger.info(f"Natural speech wake detected ('{text}').")
                                # Strip wake keyword from beginning
                                command_text = text.strip()
                                for kw in sorted(wake_keywords, key=len, reverse=True):
                                    pat = rf"^(?:{re.escape(kw)})[\s,:]+"
                                    if re.search(pat, command_text, re.IGNORECASE):
                                        command_text = re.sub(pat, "", command_text, flags=re.IGNORECASE).strip()
                                        break

                                norm_cmd = re.sub(r"[^\w\s]", "", command_text.lower()).strip()
                                if not norm_cmd or norm_cmd in wake_keywords:
                                    now = time.time()
                                    is_fresh = (now - self._last_interaction_time > 45.0) or not self._is_active_conversation
                                    self._last_interaction_time = now
                                    self._is_active_conversation = True
                                    self.set_state(AssistantState.LISTENING)

                                    if is_fresh:
                                        logger.info("Fresh conversation wake detected: speaking acknowledgment.")
                                        if self.on_transcript:
                                            self.on_transcript(text, True)
                                        asyncio.create_task(self._say_wake_acknowledgement())
                                    else:
                                        logger.info("Ongoing conversation: skipping spoken acknowledgment to save time, listening directly.")
                                        if self.on_transcript:
                                            self.on_transcript("Listening...", False)
                                else:
                                    # User spoke a full command like "Mike, open YouTube"
                                    self._last_interaction_time = time.time()
                                    self._is_active_conversation = True
                                    logger.info(f"Spoken command with wake prefix: '{command_text}'")
                                    await self._handle_user_speech(audio=None, direct_text=command_text)
                            else:
                                # Direct command support without requiring 'Mike' prefix if it matches an intent
                                if clean_t and len(clean_t) > 2:
                                    direct_intent = intent_router.match(text)
                                    if direct_intent:
                                        logger.info(f"Direct intent recognized without wake word ('{text}'). Executing...")
                                        await self._handle_user_speech(audio=None, direct_text=text)

                elif self._state == AssistantState.LISTENING:
                    # User is actively speaking; record until VAD detects SPEECH_END
                    speech_frames = [chunk]
                    self.vad.reset()
                    start_listening_time = time.time()

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

                        # Timeout: if user hasn't spoken for 6 seconds, return to IDLE
                        if not self.vad._is_speaking and (time.time() - start_listening_time > 6.0):
                            logger.info("Listening timed out with no speech. Returning to IDLE.")
                            break

                        # Safety cap: max 20 seconds
                        if time.time() - start_listening_time > 20.0:
                            break

                    if not self._is_running:
                        break

                    # Process captured speech
                    if len(speech_frames) > 6:
                        full_audio = np.concatenate(speech_frames)
                        energy = float(np.mean(np.abs(full_audio.astype(np.float32) / 32768.0)))
                        if energy > 0.0004 or self.vad._last_speech_time is not None:
                            logger.info(f"Processing speech ({len(speech_frames)} frames, energy {energy:.5f})...")
                            await self._handle_user_speech(full_audio)
                        else:
                            logger.debug("Discarding low energy buffer.")
                            self.set_state(AssistantState.IDLE)
                    else:
                        self.set_state(AssistantState.IDLE)

                elif self._state == AssistantState.SPEAKING:
                    # Ignore mic during initial TTS playback to avoid speaker loopback echo
                    if time.time() - self._speaking_start_time < 1.5:
                        self._barge_in_counter = 0
                        await asyncio.sleep(0.01)
                        continue

                    # Monitor for intentional Barge-in (requires sustained speech >=0.90)
                    vad_res = self.vad.process_chunk(chunk)
                    if vad_res["prob"] >= 0.90:
                        self._barge_in_counter += 1
                        if self._barge_in_counter >= 8:  # ~250ms of continuous speech
                            logger.info("User speech detected while speaking! Triggering barge-in...")
                            self._barge_in_counter = 0
                            self.tts.stop_playback()
                            self.set_state(AssistantState.LISTENING)
                    else:
                        self._barge_in_counter = 0

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

        self._last_interaction_time = time.time()
        self._is_active_conversation = True

        if self.on_transcript:
            self.on_transcript(text, True)

        try:
            from core.memory.history_manager import history_manager
            history_manager.add_message("user", text)
        except Exception as e:
            logger.debug(f"History record error: {e}")

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

            if intent.intent_name == "wake_up":
                now = time.time()
                is_fresh = (now - self._last_interaction_time > 45.0) or not self._is_active_conversation
                self._last_interaction_time = now
                self._is_active_conversation = True
                self.set_state(AssistantState.LISTENING)

                if is_fresh:
                    response_text = "Yes, I am here."
                    if self.on_response_chunk:
                        self.on_response_chunk(response_text)
                    self._conversation_history.append(ChatMessage(role="assistant", content=response_text))
                    try:
                        await self.tts.speak(response_text)
                    except Exception as e:
                        logger.error(f"TTS error during wake response: {e}")
                else:
                    logger.info("Ongoing conversation: skipping voice ack, listening directly.")
                return
            elif intent.intent_name == "greeting":
                response_text = (
                    "Hello Charan! I am MIKE, your autonomous multimodal desktop assistant. "
                    "I am listening and ready. You can ask me to analyze stocks, create coding projects, "
                    "control Spotify and YouTube, ask AIML questions, or query your private profile."
                )
                spoken_text = response_text
            elif intent.intent_name == "can_generate_image":
                response_text = (
                    "Yes, Charan! I have full multimodal generation capabilities. I can create "
                    "high-definition artwork, illustrations, and photos for you directly. "
                    "Just tell me what you would like to create, for example: "
                    "'Generate an illustration of a solar powered city at sunset', or 'Draw a black sports bike'."
                )
                spoken_text = response_text
            elif intent.intent_name == "image_capabilities_info":
                response_text = (
                    "No upgrades or external subscriptions are needed, Charan! My multimodal engine "
                    "is fully integrated and active right now using Flux and Gemini models. "
                    "You can ask me to generate any image, artwork, or diagram at any time."
                )
                spoken_text = response_text
            elif intent.intent_name == "cancel_action":
                response_text = "Action cancelled."
                spoken_text = response_text
            elif intent.requires_confirmation:
                response_text = intent.confirmation_prompt or "Please confirm this action."
                spoken_text = response_text
            else:
                # Direct tool execution
                tool_res = await tool_registry.execute(
                    intent.tool_name,
                    cancel_token=root_cancellation_token,
                    **intent.parameters,
                )
                response_text = tool_res.message if tool_res.success else f"I couldn't complete that: {tool_res.error}"

                # Compose natural spoken text for voice output
                if intent.tool_name == "generate_image":
                    prompt_label = intent.parameters.get("prompt", "your request")
                    spoken_text = f"I have created the illustration for {prompt_label}. The image is displayed on your screen and saved to your Media gallery."
                elif intent.tool_name == "show_latest_image":
                    spoken_text = "Here is your generated image. I have displayed it on your screen and opened it in the photo viewer."
                elif intent.tool_name in ["execute_code", "create_coding_project"]:
                    spoken_text = "I have executed the program and opened it in Visual Studio Code. The output is displayed on your screen."
                elif intent.tool_name == "manage_laptop":
                    spoken_text = self.tts.clean_text_for_speech(response_text)
                else:
                    spoken_text = self.tts.clean_text_for_speech(response_text)

            if self.on_response_chunk:
                self.on_response_chunk(response_text)

            self._conversation_history.append(ChatMessage(role="assistant", content=response_text))
            try:
                from core.memory.history_manager import history_manager
                history_manager.add_message("assistant", response_text)
            except Exception as e:
                logger.debug(f"History record error: {e}")

            try:
                await self.tts.speak(spoken_text)
            except Exception as e:
                logger.error(f"TTS error during intent response: {e}")
            finally:
                self.audio.clear_queue()
                self.vad.reset()
                if not self._cancel_token.is_set():
                    self.set_state(AssistantState.IDLE)
            return

        # 4. Stream or Generate from Brain LLM Router with full tool catalog & anti-disclaimer guardrail
        self._conversation_history.append(ChatMessage(role="user", content=text))
        self.set_state(AssistantState.THINKING)

        response_text = ""
        spoken_text = ""
        try:
            tool_defs = tool_registry.get_all_definitions()
            llm_response = await self.router.generate(
                messages=self._conversation_history,
                tools=tool_defs,
            )

            # Check for autonomous tool calls from LLM
            if llm_response.tool_calls:
                self.set_state(AssistantState.SPEAKING)
                for tc in llm_response.tool_calls:
                    logger.info(f"LLM autonomously triggered tool: {tc.name} with args {tc.arguments}")
                    tool_res = await tool_registry.execute(
                        tc.name,
                        cancel_token=root_cancellation_token,
                        **tc.arguments,
                    )
                    response_text = tool_res.message if tool_res.success else f"Action failed: {tool_res.error}"

                    if tc.name == "generate_image":
                        prompt_arg = tc.arguments.get("prompt", "your request")
                        spoken_text = f"I have created the illustration for {prompt_arg}. The image is displayed on your screen."
                    elif tc.name in ["execute_code", "create_coding_project"]:
                        spoken_text = "I have executed the program and opened it in Visual Studio Code. The output is displayed on your screen."
                    else:
                        spoken_text = self.tts.clean_text_for_speech(response_text)
            else:
                self.set_state(AssistantState.SPEAKING)
                raw_content = llm_response.content or ""

                # Anti-disclaimer guardrail: Never allow text-only or refusal disclaimers to reach user
                disclaimer_patterns = [
                    "as an ai language model",
                    "i don't have the ability to generate images",
                    "i cannot generate images",
                    "i am not able to generate images",
                    "i am a text-based assistant",
                    "i cannot display images",
                    "as a text-based ai",
                ]
                lower_resp = raw_content.lower()
                has_disclaimer = any(p in lower_resp for p in disclaimer_patterns)

                if has_disclaimer:
                    lower_query = text.lower()
                    if any(w in lower_query for w in ["image", "picture", "photo", "draw", "illustration"]):
                        clean_prompt = re.sub(
                            r"^(?:can you|please|generate|create|make|draw|show me|an?|image of|picture of)\s+",
                            "",
                            lower_query,
                        ).strip()
                        if not clean_prompt:
                            clean_prompt = "a futuristic AI assistant workspace"
                        tool_res = await tool_registry.execute("generate_image", prompt=clean_prompt)
                        response_text = tool_res.message
                        spoken_text = f"I have created the illustration for {clean_prompt}. The image is displayed on your screen."
                    else:
                        response_text = (
                            "I am MIKE, your autonomous multimodal desktop assistant. "
                            "I can generate images, write and execute code in VS Code, manage your laptop, "
                            "and assist you with all your AIML tasks. How would you like to proceed?"
                        )
                        spoken_text = response_text
                else:
                    response_text = raw_content
                    spoken_text = self.tts.clean_text_for_speech(response_text)

            if response_text and not self._cancel_token.is_set():
                if self.on_response_chunk:
                    self.on_response_chunk(response_text)
                self._conversation_history.append(ChatMessage(role="assistant", content=response_text))
                try:
                    from core.memory.history_manager import history_manager
                    history_manager.add_message("assistant", response_text)
                except Exception as e:
                    logger.debug(f"History record error: {e}")

                if not spoken_text:
                    spoken_text = self.tts.clean_text_for_speech(response_text)
                await self.tts.speak(spoken_text)

        except Exception as e:
            logger.error(f"Error generating voice response: {e}")
            if not settings.groq_api_key and not settings.gemini_api_key:
                fallback_msg = (
                    "I hear you, Charan! However, no AI brain provider is configured yet. "
                    "To enable open-ended chatting, please add your free GROQ_API_KEY or GEMINI_API_KEY "
                    "to your .env file, or start Ollama locally.\n\n"
                    "In the meantime, all local tools work! Try asking:\n"
                    "• 'Mike, who am I?' or 'Mike, what is my age?'\n"
                    "• 'Mike, analyze stock RELIANCE'\n"
                    "• 'Mike, remember that I like low latency audio'\n"
                    "• 'Mike, what do you remember about audio?'\n"
                    "• 'Mike, set volume to 50%'"
                )
            else:
                fallback_msg = (
                    f"I encountered a temporary connection issue reaching the AI provider: {str(e)[:120]}. "
                    "Please check your internet connection or retry in a moment."
                )
            if self.on_response_chunk:
                self.on_response_chunk(fallback_msg)
            self._conversation_history.append(ChatMessage(role="assistant", content=fallback_msg))
            try:
                await self.tts.speak("I encountered a connection issue reaching the AI brain. Please try again in a moment.")
            except Exception:
                pass
        finally:
            self.audio.clear_queue()
            self.vad.reset()
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
