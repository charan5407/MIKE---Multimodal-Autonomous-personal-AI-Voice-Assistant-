"""
Unit tests for MIKE Voice Pipeline: AudioStream, VAD, STT, TTS, Barge-In, and Stop Command.
"""

import time
import numpy as np
import pytest

from core.voice.audio_stream import AudioStreamManager
from core.voice.coordinator import AssistantState, VoiceCoordinator
from core.voice.stt import STTEngine
from core.voice.tts import TTSEngine
from core.voice.vad import VoiceActivityDetector
from core.voice.wake import WakeWordDetector


def test_audio_stream_init():
    stream = AudioStreamManager(sample_rate=16000, chunk_size=512)
    assert stream.sample_rate == 16000
    assert stream.chunk_size == 512
    assert stream.current_rms == 0.0
    assert not stream.is_running


def test_clean_text_for_speech():
    raw_markdown = (
        "### Header 3\n"
        "Here is **bold** and *italic* text with `code inline`.\n"
        "```python\ndef foo():\n    pass\n```\n"
        "- Bullet item 1\n"
        "[Documentation link](https://example.com/docs)\n"
    )
    cleaned = TTSEngine.clean_text_for_speech(raw_markdown)

    assert "###" not in cleaned
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "https://" not in cleaned
    assert "def foo():" not in cleaned
    assert "Code block omitted" in cleaned
    assert "Here is bold and italic text with code inline." in cleaned


def test_vad_speech_detection():
    vad = VoiceActivityDetector(sample_rate=16000, silence_timeout_ms=100)

    # 1. Complete silence chunk (zeros)
    silence = np.zeros(512, dtype=np.int16)
    res = vad.process_chunk(silence)
    assert res["event"] == "SILENCE"
    assert res["prob"] < 0.3

    # 2. Simulated speech signal (burst of sound)
    t = np.linspace(0, 512 / 16000, 512)
    tone = (np.sin(2 * np.pi * 300 * t) * 15000).astype(np.int16)

    # Process enough frames to trigger speech start
    events = [vad.process_chunk(tone)["event"] for _ in range(5)]
    assert "SPEECH_START" in events or "SPEAKING" in events

    # 3. Trailing silence to trigger SPEECH_END
    time.sleep(0.12)
    end_res = vad.process_chunk(silence)
    assert end_res["event"] == "SPEECH_END" or not end_res["is_speaking"]


def test_tts_barge_in_flag():
    tts = TTSEngine()
    assert not tts.is_speaking

    tts._is_speaking = True
    tts.stop_playback()
    assert tts._stop_event.is_set()
    assert not tts.is_speaking


def test_stop_command_logic():
    coordinator = VoiceCoordinator()
    assert coordinator._is_stop_command("Mike, stop")
    assert coordinator._is_stop_command("hey mike stop!")
    assert coordinator._is_stop_command("STOP")
    assert coordinator._is_stop_command("cancel")
    assert not coordinator._is_stop_command("play the beatles on youtube")
    assert not coordinator._is_stop_command("what is machine learning")


def test_wake_detector_toggle():
    wake = WakeWordDetector(enabled=True)
    assert wake.is_enabled
    wake.set_enabled(False)
    assert not wake.is_enabled

    # When disabled, should return False immediately
    chunk = np.zeros(512, dtype=np.int16)
    assert not wake.process_chunk(chunk)


def test_stt_engine_normalization():
    stt = STTEngine()
    assert not stt.is_loaded
    # Empty audio should return immediately without error
    empty_audio = np.array([], dtype=np.int16)
    text, lat = stt.transcribe(empty_audio)
    assert text == ""
    assert lat == 0.0

