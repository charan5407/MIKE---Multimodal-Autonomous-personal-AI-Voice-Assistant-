# MIKE: Multimodal Autonomous Agentic Desktop Voice Assistant

MIKE is a multimodal, autonomous, agentic desktop assistant designed for Windows 11. Built specifically for **Charan** (B.E./B.Tech AIML student), MIKE pairs real-time, hands-free voice interaction with desktop automation, computer vision, code synthesis, financial stock analysis, university-level tutoring, and cryptographically encrypted long-term memory.

---

## Key Highlights

- **100% Free & Open-Source Stack**: Operates entirely with free local models or free-tier APIs (Ollama, Gemini Free Tier, Groq Free Tier, DuckDuckGo, yfinance, edge-tts). Zero paid subscriptions required.
- **Natural Voice Interaction**: Real-time openWakeWord detection ("Mike" / "Hey Mike"), Silero VAD endpointing, GPU/CPU `faster-whisper` STT, and soft, calm female neural speech (`en-US-AriaNeural`, pitch `-2Hz`, rate `-4%`) with sub-50ms barge-in interruption.
- **Audio-Reactive 3D Centerpiece**: High-performance Three.js / React Three Fiber HUD featuring a metallic **"C"** emblem suspended inside 3 concentric rotating rings, particle nebula, and 6 visual states (`IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `STOPPED`, `ERROR`).
- **Autonomous Agentic Tools**: 14 distinct system capabilities spanning vision-grounded mouse control, Spotify/YouTube playback, WhatsApp messaging, financial backtesting, university exam prep, code generation, and memory retention.
- **Strict Privacy & Security Boundaries**: Three permission tiers (Tier A Safe, Tier B Reversible Logged, Tier C Strict Spoken Confirmation), immutable JSONL audit trails, prompt-injection defense envelopes, emergency stop (`Ctrl+Alt+Shift+S`, "Mike, stop", mouse corner failsafe), Fernet-encrypted profile store, and a strict **Zero UI Exposure Rule**.

---

## 14 Core Capabilities

| # | Capability | Description | Permission Tier |
|---|---|---|---|
| **1** | **YouTube Control** | Searches and opens YouTube videos via `yt-dlp` and controls playback (pause, next, mute, fullscreen). | Tier A (Safe) |
| **2** | **Music & Media** | Spotify Web API integration and global Windows hardware media keys (`VK_MEDIA_PLAY_PAUSE`, track skipping, volume). | Tier A (Safe) |
| **3** | **WhatsApp Messaging** | Voice-controlled contact resolution and messaging. Strictly reads recipient & message aloud and asks for confirmation before dispatching. | **Tier C (Sensitive Confirmation)** |
| **4** | **System Automation** | Native control over system master volume, display brightness, screen lock, application launching, clipboard, and recycling bin file management. | Tier A & B |
| **5** | **Voice Search Bar** | Real-time web search powered by DuckDuckGo with source citations, synthesized into concise voice answers. | Tier A (Safe) |
| **6** | **Stock Analyst & Forecaster** | Comprehensive technical analysis (SMA, EMA, RSI, MACD, Bollinger Bands, Support/Resistance pivots), RSS news sentiment scoring, 20-day backtesting with MAE/RMSE, and 7-day probabilistic forecasting with mandatory educational disclaimers for NSE/BSE and US stocks. | Tier A (Safe) |
| **7** | **Short-Term Context Memory** | Sliding-window conversation buffer with automated compression and rolling context summarization. | Safe / Internal |
| **8** | **Encrypted Private Profile** | Cryptographically encrypted personal store (`cryptography.fernet.Fernet`) with local key management. **Zero UI Exposure Rule**: details never render on screen. Answers strictly via audio when asked aloud. | Tier A (Audio Only) |
| **9** | **Autonomous Coding Agent** | Multi-file architectural planner, automatic file tree creation under `~/MikeProjects/`, `git init`, dependency installation, automated test-and-fix loop (max $N=3$ iterations), and automatic VS Code workspace launch. | Tier B & C |
| **10** | **3D "C" HUD Visual Engine** | Concentric metallic rings reacting to mic RMS audio and assistant state at 60 FPS in a frameless cyber glassmorphism window. | UI Display |
| **11** | **Multi-Provider LLM Brain** | Intelligent router with automatic fallback chain: **Ollama Local** (`llama3.1:8b` offline) $\rightarrow$ **Google Gemini Free Tier** (`gemini-2.0-flash` vision & tools) $\rightarrow$ **Groq Free Tier** (`llama-3.3-70b-versatile` fast tool calling). | Autonomous Router |
| **12** | **Mouse Control & Vision Grounding** | Offline Windows UI Automation (PyWinAuto UIA) with sub-50ms latency, falling back to Gemini 2.0 Flash Vision for web element localization in an **Observe-Act-Verify loop** with PyAutoGUI failsafe. | Tier B (Reversible) |
| **13** | **AIML Tutor & Code Debugger** | University exam preparation (10/15-mark answer standard), interactive quiz generation, and traceback debugger extracting file, line, error type, root cause, and verified drop-in code fixes. | Tier A (Safe) |
| **14** | **Long-Term Memory & Deletion** | SQLite memory engine with TF-IDF semantic vector similarity and keyword search. Instant memory erasure via voice command (*"Mike, forget that"* / *"forget what I just said"*). | Tier A & B (Reversible) |

---

## System Architecture

```text
Mike/
├── .env.example              # Template for environment variables and API keys
├── .env                      # Local secret keys and environment (gitignored)
├── .gitignore                # Strict privacy rules (excludes secrets, local data, models, logs)
├── README.md                 # Complete system documentation
├── requirements.txt          # Python 3.11+ dependencies
├── pytest.ini                # Pytest configuration
├── run_app.bat               # One-click launcher for Core Server + Desktop App Shell
├── run_server.py             # FastAPI + WebSocket server entry point
├── test_voice_cli.py         # Standalone voice pipeline verification script
├── prompts/
│   └── mike.md               # Master persona, tone, rules, and privacy envelopes
├── data/
│   ├── contacts.example.json # Safe template for WhatsApp contacts
│   ├── profile.example.json  # Safe template for personal profile
│   ├── secret_key.key        # Generated Fernet symmetric key (gitignored)
│   ├── profile.local.json    # Encrypted private profile storage (gitignored)
│   └── memory.db             # SQLite persistent long-term memory (gitignored)
├── core/
│   ├── config.py             # Pydantic Settings loaded from .env
│   ├── logger.py             # Structured logger with secret and PII redaction
│   ├── brain/                # Multi-Provider Router, Coding Agent, Tutor, Intent Router
│   │   ├── base.py           # Provider interface, LLMRequest, LLMResponse
│   │   ├── router.py         # Automatic fallback engine (Ollama -> Gemini -> Groq)
│   │   ├── intent_router.py  # Fast-path regex matching (<10ms) & confirmation tracker
│   │   ├── coding/           # Autonomous project builder & VS Code integration
│   │   └── tutor/            # University exam mode, quiz generator, traceback debugger
│   ├── voice/                # Real-time Voice Pipeline
│   │   ├── audio_stream.py   # SoundDevice ring buffer with RMS energy metering
│   │   ├── wake_word.py      # openWakeWord engine ("Mike" / "Hey Mike")
│   │   ├── vad.py            # Silero VAD / adaptive SNR voice activity endpointing
│   │   ├── stt.py            # faster-whisper local streaming STT (GPU / CPU)
│   │   ├── tts.py            # edge-tts soft calm female voice (en-US-AriaNeural)
│   │   └── coordinator.py    # Voice loop orchestration & sub-50ms barge-in
│   ├── server/               # Core IPC Server
│   │   ├── app.py            # FastAPI REST endpoints & tool initialization
│   │   └── ws.py             # WebSocket broadcasting (state, RMS, transcript, tools)
│   ├── security/             # Security & Privacy Framework
│   │   ├── permissions.py    # Tier A, Tier B, Tier C security gatekeeper
│   │   ├── audit.py          # Structured JSONL audit logging (logs/audit.jsonl)
│   │   ├── profile.py        # Fernet encryption & private profile manager
│   │   ├── profile_tool.py   # Audio-only private profile querying tool
│   │   └── sanitizer.py      # Prompt-injection defense data envelopes
│   ├── memory/               # Short & Long-Term Memory Engine
│   │   ├── short_term.py     # Rolling conversation buffer with auto-summarization
│   │   ├── long_term.py      # SQLite store with TF-IDF semantic vector recall
│   │   └── tools.py          # RememberTool, RecallMemoryTool, ForgetLastTool
│   └── tools/                # Extensible Tool Engine
│       ├── base.py           # BaseTool class with Pydantic schema validation
│       ├── cancellation.py   # Cooperative CancellationToken & corner failsafe
│       ├── registry.py       # Tool discovery and activity broadcasting
│       ├── system/           # Volume, brightness, lock, apps, clipboard, files
│       ├── media/            # YouTube and Spotify playback tools
│       ├── whatsapp/         # WhatsApp voice messenger with Tier C confirmation
│       ├── mouse/            # PyWinAuto UIA + Gemini Flash Vision mouse control
│       ├── search/           # DuckDuckGo web search tool
│       └── finance/          # Technical indicators, sentiment, and backtesting
├── desktop/                  # Electron + React HUD Application Shell
│   ├── package.json          # Vite + Electron Builder build scripts
│   ├── electron/             # Main process, system tray, global shortcuts
│   │   ├── main.cjs          # Window management, tray icon, shortcuts
│   │   └── preload.cjs       # Secure IPC bridge
│   └── src/                  # React 18 + Three.js Frontend
│       ├── App.tsx           # Cyber glassmorphism layout
│       ├── components/
│       │   ├── hud/          # 3D "C" centerpiece, concentric rings, particle nebula
│       │   ├── SettingsModal.tsx # Zero UI exposure settings modal
│       │   ├── ToolActivityPanel.tsx # Real-time tool execution stream
│       │   ├── VoiceSearchBar.tsx # Search bar input
│       │   └── TranscriptPanel.tsx # Dialogue transcript
│       └── hooks/
│           └── useWebSocket.ts # Live WebSocket connection to Core Server
└── tests/                    # Comprehensive Automated Test Suite (77 Tests)
    ├── test_coding_agent.py
    ├── test_llm_router.py
    ├── test_media_whatsapp.py
    ├── test_memory_profile.py
    ├── test_mouse_vision.py
    ├── test_search_tutor.py
    ├── test_server.py
    ├── test_stock_analyst.py
    ├── test_system_tools.py
    ├── test_tools.py
    └── test_voice_pipeline.py
```

---

## Security & Privacy Framework

### 1. Permission Tiers
- **Tier A (Safe)**: Executes immediately without confirmation (read-only queries, system status, web search, volume level, time).
- **Tier B (Reversible)**: Executes automatically and records an immutable audit log entry with rollback metadata (creating files, launching applications, clipboard writes, remembering facts).
- **Tier C (Sensitive)**: **Strictly requires explicit spoken or on-screen confirmation from Charan** (sending WhatsApp messages, deleting files, power state changes). If denied or timed out after 30 seconds, the action is rejected immediately.

### 2. Zero UI Exposure Rule
Charan's private personal details (full name, date of birth, age, college/degree, personal project paths) are stored strictly inside a `cryptography.fernet.Fernet` encrypted file (`data/profile.local.json`) protected by `data/secret_key.key`.
- The desktop UI has **no component or input field** rendering these values.
- WebSocket state broadcasts **never leak** raw profile values.
- MIKE reveals profile facts **only when Charan explicitly asks aloud** (e.g. *"Mike, what is my age?"*).

### 3. Emergency Stop & Corner Failsafe
- Spoken command: *"Mike, stop"*
- Global shortcut: **`Ctrl + Alt + Shift + S`**
- Mouse corner failsafe: Slamming the mouse pointer to any of the 4 screen corners activates `pyautogui.FAILSAFE = True` abort.
- Action: Halts running tools via [`CancellationToken`](file:///c:/Users/ASUS/OneDrive/Desktop/Mike/core/tools/cancellation.py), releases held mouse buttons and modifier keys, rolls back reversible actions, and speaks *"Stopped."*

---

## Quickstart & Setup

### Prerequisites
1. **Windows 10 or 11 (64-bit)**
2. **Python 3.11+**
3. **Node.js 18+ & npm**
4. Optional: **Ollama** (for local offline LLM)

### Installation
```powershell
# 1. Clone repository
git clone https://github.com/charan5407/Mike.git
cd Mike

# 2. Set up Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Set up Desktop frontend dependencies
npm --prefix desktop install

# 4. Configure environment
cp .env.example .env
# Edit .env with your free Gemini/Groq API keys and local preferences
```

### Running the Application

**Option A: One-Click App Launcher**
```powershell
.\run_app.bat
```

**Option B: Manual Terminal Execution**
```powershell
# Terminal 1: Core FastAPI + WebSocket Server
.\.venv\Scripts\python.exe run_server.py

# Terminal 2: Electron Desktop HUD
npm --prefix desktop run dev
# Or run with Electron app shell
npm --prefix desktop run electron:dev
```

### Building the Windows Installer (.exe)
```powershell
npm --prefix desktop run electron:build
```
The compiled setup executable (`MIKE Setup 0.1.0.exe`) will be generated inside `desktop/release/`.

---

## Testing & Verification

The system includes a 100% passing automated test suite covering all 12 implementation phases:

```powershell
# Run the complete test suite
.\.venv\Scripts\pytest.exe -v
```

```text
============================= 77 passed in 15.97s =============================
```

### Test Coverage Breakdown
- `tests/test_voice_pipeline.py`: openWakeWord, Silero VAD, faster-whisper STT, edge-tts synthesis, barge-in halting.
- `tests/test_server.py`: FastAPI health checks, REST actions, WebSocket real-time audio RMS broadcasting.
- `tests/test_llm_router.py`: Ollama offline fallback $\rightarrow$ Gemini Free $\rightarrow$ Groq Free failover.
- `tests/test_tools.py`: Permission tiers A/B/C, confirmation timeout, prompt injection sanitizer, cancellation tokens.
- `tests/test_system_tools.py`: Volume, brightness, workstation lock, application launch, clipboard, file manager.
- `tests/test_media_whatsapp.py`: YouTube search/controls, Spotify media keys, WhatsApp contact resolution & voice confirmation.
- `tests/test_mouse_vision.py`: PyWinAuto UIA control locator, Gemini 2.0 Flash Vision element grounding, Observe-Act-Verify loop.
- `tests/test_search_tutor.py`: DuckDuckGo search citations, university exam mode, quiz generator, traceback code debugger.
- `tests/test_coding_agent.py`: Autonomous project planner, file tree synthesizer, git init, automated test-and-fix loop.
- `tests/test_stock_analyst.py`: NSE/BSE & US ticker normalization, technical indicators, news sentiment, backtesting forecaster.
- `tests/test_memory_profile.py`: Fernet encryption/decryption, Zero UI exposure, short-term summarization, SQLite long-term memory, TF-IDF recall, "forget that" deletion.

---

## License & Attribution

Developed with pride by **Charan** (B.E./B.Tech AIML student).
Licensed under the **MIT License**. Strictly for educational and personal autonomous assistance.
