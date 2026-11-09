@echo off
set ELECTRON_RUN_AS_NODE=
title MIKE Desktop Assistant - Autonomous Agentic HUD
echo ==============================================================================
echo Launching MIKE Desktop Assistant (Core Server + Electron HUD Shell)...
echo ==============================================================================

if not exist ".venv\Scripts\python.exe" (
    echo Error: Python virtual environment not found in .venv\
    pause
    exit /b 1
)

echo [1/2] Starting Python Core Server (FastAPI + WebSocket on http://127.0.0.1:8765)...
start "MIKE Core Server" /min ".venv\Scripts\python.exe" run_server.py

echo [2/2] Launching Desktop App Shell...
cd desktop
npm run electron:dev

pause

