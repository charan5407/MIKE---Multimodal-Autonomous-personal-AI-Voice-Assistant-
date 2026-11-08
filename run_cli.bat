@echo off
title MIKE Assistant - CLI Mode
echo ==============================================================================
echo Starting MIKE Assistant CLI...
echo ==============================================================================
if not exist ".venv\Scripts\python.exe" (
    echo Error: Python virtual environment not found in .venv\
    pause
    exit /b 1
)
".venv\Scripts\python.exe" cli_chat.py
pause

