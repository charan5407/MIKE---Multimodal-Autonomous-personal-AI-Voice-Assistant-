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

:: Free ports 5173 & 8765 if lingering from previous run
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 5173,8765 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo [1/2] Starting Python Core Server (FastAPI + WebSocket on http://127.0.0.1:8765)...
start "MIKE Core Server" /min ".venv\Scripts\python.exe" run_server.py

echo [2/2] Launching Desktop App Shell...
cd desktop
npm run electron:dev

pause

