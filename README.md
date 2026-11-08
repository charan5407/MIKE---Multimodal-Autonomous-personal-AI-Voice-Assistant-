# MIKE: Multimodal Autonomous Agentic Desktop Voice Assistant

MIKE is an autonomous, agentic desktop assistant designed for Windows with an audio-reactive 3D HUD centerpiece, voice pipeline (wake word, VAD, local streaming STT, and calm female TTS), multi-provider LLM brain (Ollama offline fallback $\rightarrow$ Gemini Free $\rightarrow$ Groq Free), desktop app shell with system tray icon, tool execution framework with permission tiers, and system automation capabilities.

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
├── cli_chat.py
├── test_voice_cli.py
├── prompts/
│   └── mike.md               # MIKE persona, tone, rules, and safety boundaries
├── data/
│   ├── contacts.example.json # Dummy template for WhatsApp contacts
│   └── profile.example.json  # Dummy template for personal profile
├── core/
│   ├── config.py             # Pydantic Settings loading from .env
│   ├── logger.py             # Structured logger with secret/PII redaction
│   ├── brain/                # Multi-provider LLM routing (Phase 1)
│   ├── voice/                # Real-time Voice Pipeline (Phase 2)
│   ├── server/               # FastAPI + WebSocket Core IPC Server (Phase 3)
│   ├── security/             # Security, Permission Tiers & Audit (Phase 5)
│   │   ├── permissions.py    # Tier A (Safe), Tier B (Logged), Tier C (Strict Confirm)
│   │   ├── audit.py          # Structured JSONL audit logger (logs/audit.jsonl)
│   │   └── sanitizer.py      # Prompt injection defenses & untrusted data envelopes
│   └── tools/                # Tool Execution Engine (Phase 5)
│       ├── base.py           # BaseTool interface & Pydantic JSON Schema generator
│       ├── cancellation.py   # CancellationToken & input release failsafe (pyautogui)
│       └── registry.py       # Tool discovery, permission enforcement, WebSocket broadcast
├── desktop/                  # Desktop Application Shell
│   ├── src/
│   │   ├── App.tsx           # HUD layout & controls
│   │   ├── components/
│   │   │   ├── hud/          # 3D HUD (Three.js / React Three Fiber)
│   │   │   ├── ToolActivityPanel.tsx # Live tool activity stream (Phase 5)
│   │   │   ├── VoiceSearchBar.tsx
│   │   │   ├── TranscriptPanel.tsx
│   │   │   └── SettingsModal.tsx
└── tests/
    ├── test_llm_router.py    # LLM Router & prompt tests
    ├── test_voice_pipeline.py # Voice pipeline unit tests
    ├── test_server.py        # FastAPI & WebSocket server tests
    └── test_tools.py         # Permission, audit, cancellation, & sanitizer tests
```

---

## Permission Tiers & Security Framework

MIKE enforces 3 distinct permission tiers for every system action:
- **Tier A (Safe)**: Runs automatically without confirmation (read-only queries, system status, web search, volume level, time).
- **Tier B (Reversible)**: Runs automatically and records an immutable audit trail with rollback metadata (creating files, launching apps, clipboard operations).
- **Tier C (Sensitive)**: **STRICTLY REQUIRES explicit spoken or on-screen confirmation from Charan** (sending WhatsApp messages, deleting files, locking/shutting down workstation, executing code). If denied or timed out, the action is rejected immediately.

### Prompt-Injection Defense
All content ingested from external sources (web pages, WhatsApp messages, local files, screen text) is enclosed inside an immutable data envelope by [`PromptSanitizer`](file:///c:/Users/ASUS/OneDrive/Desktop/Mike/core/security/sanitizer.py). Content is strictly treated as data and never as instructions.

### Emergency Stop & Failsafe
- Saying `"Mike, stop"`, pressing **`Ctrl+Alt+Shift+S`**, or slamming the mouse to any screen corner triggers immediate cancellation:
  - Active tools are halted via [`CancellationToken`](file:///c:/Users/ASUS/OneDrive/Desktop/Mike/core/tools/cancellation.py).
  - All held mouse buttons and modifier keys are released.
  - Reversible actions are rolled back.
  - Voice coordinator immediately speaks *"Stopped."*

---

## Project Status

### Completed Phases:
- [x] **Phase 1**: Core Scaffold, Config, Logging, LLM Router (Ollama $\rightarrow$ Gemini $\rightarrow$ Groq)
- [x] **Phase 2**: Voice Pipeline (openWakeWord, Silero VAD, faster-whisper, calm TTS, barge-in)
- [x] **Phase 3**: Desktop App Shell (Electron + React 18 + TypeScript + Vite, System Tray, Settings)
- [x] **Phase 4**: 3D "C" HUD with Audio-Reactive Concentric Rings & 60 FPS WebGL Engine
- [x] **Phase 5**: Tool Framework, Permission Tiers (A/B/C), Audit Log, Cancellation & Sanitizer
- [x] **25/25 automated unit tests passing 100%**
