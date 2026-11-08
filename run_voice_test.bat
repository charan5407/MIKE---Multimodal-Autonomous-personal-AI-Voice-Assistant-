@echo off
title MIKE Voice Pipeline Verification - Phase 2
echo ==============================================================================
echo Starting MIKE Voice Pipeline Verification...
echo (Microphone, VAD, STT, Soft-Spoken TTS, Barge-in, Stop Command)
echo ==============================================================================
if not exist ".venv\Scripts\python.exe" (
    echo Error: Python virtual environment not found in .venv\
    pause
    exit /b 1
)
".venv\Scripts\python.exe" test_voice_cli.py
pause
