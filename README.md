# MIKE: Multimodal Autonomous Agentic Desktop Voice Assistant

MIKE is an autonomous, agentic desktop assistant designed for Windows with an audio-reactive 3D HUD centerpiece, voice pipeline (wake word, VAD, local streaming STT, and calm female TTS), multi-provider LLM brain (Ollama offline fallback $\rightarrow$ Gemini Free $\rightarrow$ Groq Free), desktop app shell with system tray icon, and system automation capabilities.

---

## Architecture Overview

```text
Mike/
├── .env.example              # Template for all environment variables & API keys
├── .env                      # Local environment file (gitignored)
├── .gitignore                # Strict privacy rules (excludes .env, local data, logs, models)
├── README.md                 # Setup and architecture documentation
├── requirements.txt          # Python 3.11+ dependencies
├── pytest.ini                # Pytest configuration
├── run_app.bat               # One-click launcher for Core Server + Desktop App Shell
├── run_cli.bat               # One-click CLI chat launcher
├── run_voice_test.bat        # One-click voice pipeline verification
├── run_server.py             # FastAPI + WebSocket server runner
├── cli_chat.py               # Interactive CLI for testing prompt and providers
├── test_voice_cli.py         # Voice pipeline interactive test (VAD, STT, TTS, Barge-in)
├── prompts/
│   └── mike.md               # MIKE persona, tone, rules, and safety boundaries
├── data/
│   ├── contacts.example.json # Dummy template for WhatsApp contacts
│   └── profile.example.json  # Dummy template for personal profile
├── core/
│   ├── config.py             # Pydantic Settings loading from .env
│   ├── logger.py             # Structured logger with secret/PII redaction
│   ├── brain/                # Multi-provider LLM routing
│   │   ├── base.py           # Provider interface, message, and tool definitions
│   │   ├── router.py         # Automatic fallback engine (Ollama -> Gemini -> Groq)
│   │   └── providers/        # Concrete provider implementations
│   ├── voice/                # Real-time Voice Pipeline (Phase 2)
│   │   ├── audio_stream.py   # sounddevice continuous microphone capture & RMS visualizer
│   │   ├── vad.py            # Voice Activity Detection (silence endpointing & energy tracking)
│   │   ├── wake.py           # openWakeWord engine ("Mike" / "Hey Mike")
│   │   ├── stt.py            # Local faster-whisper with NVIDIA CUDA support
│   │   ├── tts.py            # Soft, calm female TTS (edge-tts / Piper) with barge-in
│   │   └── coordinator.py    # Master state machine (IDLE -> LISTENING -> THINKING -> SPEAKING)
│   └── server/               # FastAPI + WebSocket Core IPC Server (Phase 3)
│       ├── app.py            # REST API endpoints & background event broadcasters
│       └── ws.py             # WebSocket connection manager (RMS, state, transcripts)
├── desktop/                  # Desktop Application Shell (Phase 3)
│   ├── package.json          # React 18, Vite, TypeScript, Tailwind, Electron
│   ├── vite.config.ts        # Vite configuration
│   ├── electron/
│   │   ├── main.cjs          # System tray icon, global shortcuts, frameless window
│   │   └── preload.cjs       # Secure IPC bridge (tray, always-on-top, boot)
│   └── src/
│       ├── App.tsx           # Glassmorphism HUD layout & header
│       ├── types.ts          # Strongly typed UI state models
│       ├── hooks/
│       │   └── useWebSocket.ts # Live auto-reconnecting WebSocket hook (RMS & state)
│       └── components/
│           ├── CenterpiecePreview.tsx # Concentric rotating rings + metallic "C" emblem
│           ├── VoiceSearchBar.tsx     # Voice & typed search bar with mic & stop
│           ├── TranscriptPanel.tsx    # Live transcript & AI response streaming
│           └── SettingsModal.tsx      # Settings drawer (Wake word, Mic, Model, Hotkeys)
└── tests/
    ├── test_llm_router.py    # LLM Router & prompt tests
    ├── test_voice_pipeline.py # Voice pipeline unit tests
    └── test_server.py        # FastAPI endpoints & WebSocket server tests
```

---

## Quickstart & Launch Instructions

### 1. Launch the Desktop Application (FastAPI Core Server + Electron HUD)
Double-click [`run_app.bat`](file:///c:/Users/ASUS/OneDrive/Desktop/Mike/run_app.bat) or run from PowerShell:
```powershell
.\run_app.bat
```
*(This starts the Python Core Server in the background on port `8765` and launches the Electron HUD with system tray icon).*

### 2. Launch Background Python Server Standalone
```powershell
.\.venv\Scripts\python.exe run_server.py
```
View API docs: `http://127.0.0.1:8765/docs`

### 3. Launch Frontend in Browser Dev Mode
```powershell
cd desktop
npm run dev
```
Open `http://localhost:5173` in your browser to view the interactive HUD and settings.

### 4. Run the Full Test Suite
```powershell
.\.venv\Scripts\pytest.exe -v tests/
```

---

## Global Hotkeys & Desktop Controls

| Hotkey | Action | Scope |
| :--- | :--- | :--- |
| **`Ctrl + Alt + Shift + S`** | **Emergency Stop** (halts TTS, releases controls, cancels task) | Global (System-wide) |
| **`Ctrl + Space`** | **Push to Talk** (activates listening mode) | Global (System-wide) |
| **System Tray Icon ("C")** | Left click toggles HUD visibility; Right click opens context menu | System Tray |

---

## Project Status

### Phase 1: Complete
- [x] Project scaffolding & Git privacy configuration (`.gitignore`, `.env.example`, `data/*.example.json`)
- [x] Pydantic Settings configuration (`core/config.py`)
- [x] Structured logger with secret and PII redaction filter (`core/logger.py`)
- [x] Multi-provider LLM Router with automated fallback & streaming (`core/brain/router.py`)

### Phase 2: Complete
- [x] Continuous microphone capture & live RMS amplitude (`core/voice/audio_stream.py`)
- [x] Voice Activity Detection (VAD) with silence endpointing (`core/voice/vad.py`)
- [x] Wake-word detection engine for "Mike" / "Hey Mike" (`core/voice/wake.py`)
- [x] Local Speech-to-Text with faster-whisper on CUDA / CPU (`core/voice/stt.py`)
- [x] Soft, calm female Text-to-Speech (edge-tts / Piper) with sub-50ms barge-in support (`core/voice/tts.py`)
- [x] Emergency stop logic & voice command interception

### Phase 3: Complete
- [x] FastAPI Core Application with REST & WebSocket IPC endpoints (`core/server/app.py`, `core/server/ws.py`)
- [x] Real-time 30fps RMS amplitude & state streaming to WebSocket
- [x] Electron + React + TypeScript + Vite Desktop App Shell (`desktop/`)
- [x] Windows System Tray Icon with "C" brand emblem and context menu (`desktop/electron/main.cjs`)
- [x] Global system hotkeys (`Ctrl+Alt+Shift+S` Emergency Stop, `Ctrl+Space` Push-to-Talk)
- [x] Full Settings Modal (Wake word toggle, Mic selector, Model choice, Start on boot, Always-on-top, Permission tiers)
- [x] Voice Search Bar & Live Transcript panels
- [x] 18 automated unit tests passing 100% (`tests/`)
