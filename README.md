# MIKE: Multimodal Autonomous Agentic Desktop Voice Assistant

MIKE is an autonomous, agentic desktop assistant designed for Windows with an audio-reactive 3D HUD centerpiece, voice pipeline (wake word, VAD, local streaming STT, and calm female TTS), multi-provider LLM brain (Ollama offline fallback $\rightarrow$ Gemini Free $\rightarrow$ Groq Free), and system automation capabilities.

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
├── run_cli.bat               # One-click launcher for the CLI test interface
├── run_voice_test.bat        # One-click launcher for the interactive voice test
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
│   │       ├── ollama_provider.py  # Offline local LLM via Ollama REST
│   │       ├── gemini_provider.py  # Google Gemini 2.0 / 1.5 Flash client
│   │       └── groq_provider.py    # Groq Llama 3.3 70B fast inference client
│   └── voice/                # Real-time Voice Pipeline (Phase 2)
│       ├── audio_stream.py   # sounddevice continuous microphone capture & RMS visualizer
│       ├── vad.py            # Voice Activity Detection (silence endpointing & energy tracking)
│       ├── wake.py           # openWakeWord engine ("Mike" / "Hey Mike")
│       ├── stt.py            # Local faster-whisper with NVIDIA CUDA acceleration
│       ├── tts.py            # Soft, calm female TTS (edge-tts / Piper) with barge-in
│       └── coordinator.py    # Master state machine (IDLE -> LISTENING -> THINKING -> SPEAKING)
└── tests/
    ├── test_llm_router.py    # Unit tests for config, logger, and router fallback
    └── test_voice_pipeline.py # Unit tests for audio, VAD, STT, TTS, barge-in, stop
```

---

## Free-Tier API Setup

MIKE is designed to operate on **100% free or open-source infrastructure**:

1. **Google Gemini Free Tier** (Vision & Native Tool Calling):
   - Get your free key at: [Google AI Studio](https://aistudio.google.com/)
   - Add to `.env`: `GEMINI_API_KEY=your_key_here`
2. **Groq Free Tier** (Ultra-low latency inference & Tool Calling):
   - Get your free key at: [Groq Console](https://console.groq.com/)
   - Add to `.env`: `GROQ_API_KEY=your_key_here`
3. **Ollama Local** (Offline LLM):
   - Download & install [Ollama](https://ollama.com/)
   - Run in terminal: `ollama pull llama3.1:8b` (or `qwen2.5:7b`)
4. **faster-whisper & openWakeWord**:
   - 100% local, runs on NVIDIA GPU via CUDA with automatic CPU int8 fallback.
5. **edge-tts**:
   - Free Microsoft Neural TTS (`en-US-AriaNeural`, `en-GB-SoniaNeural`), tuned for soft, calm delivery.

---

## Quickstart & Run Instructions

### 1. Launch Interactive Voice Pipeline Verification
Run with the batch launcher:
```powershell
.\run_voice_test.bat
# Or via powershell:
.\.venv\Scripts\python.exe test_voice_cli.py
```

### 2. Launch CLI Mode (Chat & LLM Router)
```powershell
.\run_cli.bat
# Or via powershell:
.\.venv\Scripts\python.exe cli_chat.py
```

### 3. Run the Automated Unit Test Suite
```powershell
.\.venv\Scripts\pytest.exe -v tests/
```

---

## Project Status

### Phase 1: Complete
- [x] Project scaffolding & Git privacy configuration (`.gitignore`, `.env.example`, `data/*.example.json`)
- [x] Pydantic Settings configuration (`core/config.py`)
- [x] Structured logger with secret and PII redaction filter (`core/logger.py`)
- [x] MIKE system prompt and persona definitions (`prompts/mike.md`)
- [x] Multi-provider LLM Router with automated fallback & streaming (`core/brain/router.py`)
- [x] Interactive CLI chat interface (`cli_chat.py`)

### Phase 2: Complete
- [x] Real-time microphone audio capture stream with live RMS amplitude (`core/voice/audio_stream.py`)
- [x] Voice Activity Detection (VAD) with silence endpointing (`core/voice/vad.py`)
- [x] Wake-word detection engine for "Mike" / "Hey Mike" (`core/voice/wake.py`)
- [x] Local Speech-to-Text with faster-whisper on CUDA / CPU (`core/voice/stt.py`)
- [x] Soft, calm female Text-to-Speech (edge-tts / Piper) with sub-50ms barge-in support (`core/voice/tts.py`)
- [x] Master Voice Coordinator state machine (`core/voice/coordinator.py`)
- [x] Voice Stop Command: Immediate interruption and cancellation on saying "Mike, stop"
- [x] Interactive verification tool (`test_voice_cli.py`) & launcher (`run_voice_test.bat`)
- [x] 13 automated unit tests passing 100% (`tests/test_llm_router.py`, `tests/test_voice_pipeline.py`)
