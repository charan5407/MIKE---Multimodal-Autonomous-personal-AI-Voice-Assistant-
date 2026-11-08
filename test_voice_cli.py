"""
MIKE - Interactive Voice Pipeline Verification & Demonstration Script.
Tests: Audio input, VAD speech detection, STT transcription, TTS with barge-in, and stop commands.
"""

import asyncio
import sys
import time
import numpy as np

from core.logger import logger
from core.voice.audio_stream import AudioStreamManager
from core.voice.coordinator import AssistantState, VoiceCoordinator
from core.voice.stt import stt_engine
from core.voice.tts import tts_engine
from core.voice.vad import VoiceActivityDetector
from core.voice.wake import wake_detector


async def test_tts_and_barge_in():
    print("\n[1/4] Testing Soft Calm Female TTS & Barge-in Interruption...")
    test_phrase = (
        "Hello Charan. I am MIKE, your personal assistant. "
        "My voice has been tuned to be soft, calm, and natural. "
        "I am currently speaking a longer sentence to demonstrate the barge in capability. "
        "If you speak or press Enter right now, I will stop speaking immediately."
    )
    print("Synthesizing speech via edge-tts (en-US-AriaNeural, soft-pitch)...")
    audio_bytes = await tts_engine.synthesize_to_bytes(test_phrase)
    if not audio_bytes:
        print("[ERROR] TTS synthesis failed.")
        return

    print(f"Synthesis successful ({len(audio_bytes)} bytes). Playing audio now...")
    print(">>> Press ENTER or speak to trigger Barge-in! <<<")

    loop = asyncio.get_running_loop()

    # Play audio in background
    play_task = asyncio.create_task(
        loop.run_in_executor(None, tts_engine.play_audio_bytes, audio_bytes)
    )

    # Monitor for keypress to test barge-in
    def wait_for_interrupt():
        try:
            sys.stdin.readline()
            if tts_engine.is_speaking:
                print("\n[Barge-In] Interruption signal received! Halting playback...")
                tts_engine.stop_playback()
        except Exception:
            pass

    key_task = asyncio.create_task(loop.run_in_executor(None, wait_for_interrupt))

    await play_task
    key_task.cancel()
    print("[1/4] TTS & Barge-in test completed.\n")


def test_microphone_and_vad():
    print("[2/4] Testing Microphone Capture & Voice Activity Detection (VAD)...")
    devices = AudioStreamManager.list_input_devices()
    print("Available Input Devices:")
    for d in devices:
        print(f"  [{d['index']}] {d['name']}")

    stream = AudioStreamManager()
    vad = VoiceActivityDetector(silence_timeout_ms=700)

    try:
        stream.start()
        print("\nMicrophone active! Speak into your microphone now (Recording for 6 seconds)...")
        start = time.time()
        while time.time() - start < 6.0:
            chunk = stream.read_chunk(timeout=0.05)
            if chunk is None:
                continue

            vad_res = vad.process_chunk(chunk)
            rms = stream.current_rms
            meter = "#" * int(rms * 30)

            event = vad_res["event"]
            if event != "SILENCE":
                print(f"\r[VAD: {event:<12}] RMS: {rms:.2f} |{meter:<30}| Prob: {vad_res['prob']:.2f}", end="", flush=True)
            else:
                print(f"\r[VAD: SILENCE     ] RMS: {rms:.2f} |{meter:<30}|", end="", flush=True)

            time.sleep(0.02)
        print("\n[2/4] Microphone & VAD test completed.\n")
    finally:
        stream.stop()


def test_stt_transcription():
    print("[3/4] Testing Speech-to-Text with faster-whisper...")
    print("Loading faster-whisper model...")
    stt_engine.load_model()

    stream = AudioStreamManager()
    vad = VoiceActivityDetector(silence_timeout_ms=800)
    stream.start()

    print("Please say a short phrase (e.g. 'Hello Mike, how is the weather today?')...")
    frames = []
    recording = False

    try:
        start_wait = time.time()
        while time.time() - start_wait < 10.0:
            chunk = stream.read_chunk(timeout=0.05)
            if chunk is None:
                continue

            res = vad.process_chunk(chunk)
            if res["event"] == "SPEECH_START":
                recording = True
                print("\n[Speech Detected! Recording...]")
            if recording:
                frames.append(chunk)
                if res["event"] == "SPEECH_END":
                    print("[Speech Ended. Transcribing audio...]")
                    break

        if frames:
            full_audio = np.concatenate(frames)
            text, latency = stt_engine.transcribe(full_audio)
            print(f"Transcription: \"{text}\"")
            print(f"Transcription Latency: {latency:.1f}ms")
        else:
            print("[No speech detected within 10 seconds]")
        print("[3/4] STT test completed.\n")
    finally:
        stream.stop()


def test_stop_command():
    print("[4/4] Testing Stop Command Logic...")
    test_cases = [
        ("Mike, stop", True),
        ("hey mike stop", True),
        ("stop", True),
        ("please play YouTube music", False),
        ("cancel", True),
    ]
    coordinator = VoiceCoordinator()
    all_passed = True
    for phrase, expected in test_cases:
        actual = coordinator._is_stop_command(phrase)
        status = "PASSED" if actual == expected else "FAILED"
        print(f"  Phrase: '{phrase:<25}' -> Expected Stop: {expected:<5} | Got: {actual:<5} [{status}]")
        if actual != expected:
            all_passed = False

    if all_passed:
        print("[4/4] Stop command test PASSED.\n")
    else:
        print("[4/4] Stop command test FAILED.\n")


async def main():
    print("================================================================================")
    print("   MIKE VOICE PIPELINE VERIFICATION (PHASE 2)")
    print("   Owner: Charan | Testing Audio, VAD, STT, TTS, Barge-in & Stop")
    print("================================================================================")

    test_stop_command()
    await test_tts_and_barge_in()
    test_microphone_and_vad()
    test_stt_transcription()

    print("All Phase 2 interactive checks finished!")


if __name__ == "__main__":
    asyncio.run(main())

