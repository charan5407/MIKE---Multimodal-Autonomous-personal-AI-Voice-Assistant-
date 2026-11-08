# MIKE: Multimodal Autonomous Agentic Desktop Voice Assistant

MIKE is an autonomous, agentic desktop assistant designed for Windows with an audio-reactive 3D HUD centerpiece, voice pipeline (wake word, VAD, local streaming STT, and calm female TTS), multi-provider LLM brain (Ollama offline fallback $\rightarrow$ Gemini Free $\rightarrow$ Groq Free), and system automation capabilities.

---

## Architecture Overview

```text
Mike/
├── .env.example              # Template for all environment variables & API keys
├── .gitignore                # Strict privacy rules (excludes .env, local data, logs, models)
├── README.md                 # Setup and architecture documentation
├── requirements.txt          # Python 3.11+ dependencies
├── pytest.ini                # Pytest configuration
├── run_cli.bat               # One-click launcher for the CLI test interface
├── prompts/
│   └── mike.md               # MIKE persona, tone, rules, and safety boundaries
├── data/
│   ├── profile.example.json  # Dummy template for personal profile
│   └── contacts.example.json # Dummy template for WhatsApp contacts
├── core/
│   ├── config.py             # Pydantic Settings loading from .env
│   ├── logger.py             # Structured logger with secret/PII redaction
│   └── brain/                # Multi-provider LLM routing
│       ├── base.py           # Provider interface, message, and tool definitions
│       ├── router.py         # Automatic fallback engine (Ollama -> Gemini -> Groq)
│       └── providers/        # Concrete provider implementations
│           ├── ollama_provider.py  # Offline local LLM via Ollama REST
│           ├── gemini_provider.py  # Google Gemini 2.0 / 1.5 Flash client
│           └── groq_provider.py    # Groq Llama 3.3 70B fast inference client
├── cli_chat.py               # Interactive CLI for testing prompt and providers
└── tests/
    └── test_llm_router.py    # Unit tests for config, logger, and router fallback
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
   - Starts automatically at `http://localhost:11434` without any API keys.

---

## Quickstart & Run Instructions

### 1. Configure `.env`
Copy `.env.example` to `.env` (already created locally) and paste your free `GEMINI_API_KEY` or `GROQ_API_KEY`:
```ini
LLM_PRIMARY_PROVIDER=gemini
LLM_FALLBACK_PROVIDERS=groq,ollama

GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_...
```

### 2. Launch CLI Mode
Run the interactive CLI using the batch runner or Python:
```powershell
.\run_cli.bat
# Or via powershell:
.\.venv\Scripts\python.exe cli_chat.py
```

### 3. Run the Unit Test Suite
```powershell
.\.venv\Scripts\pytest.exe -v tests/
```

---

## Current Status: Phase 1 Complete
- [x] Project scaffolding & Git privacy configuration (`.gitignore`, `.env.example`, `data/*.example.json`)
- [x] Pydantic Settings configuration (`core/config.py`)
- [x] Structured logger with secret and PII redaction filter (`core/logger.py`)
- [x] MIKE system prompt and persona definitions (`prompts/mike.md`)
- [x] LLM Provider interfaces and implementations:
  - Local Ollama Provider (`core/brain/providers/ollama_provider.py`)
  - Google Gemini Provider (`core/brain/providers/gemini_provider.py`)
  - Groq Provider (`core/brain/providers/groq_provider.py`)
- [x] Multi-provider LLM Router with automated fallback & streaming (`core/brain/router.py`)
- [x] Interactive CLI chat interface (`cli_chat.py`) with commands (`/status`, `/provider`, `/stream`, `/reload`, `/test-tools`)
- [x] Unit test suite passing 100% (`tests/test_llm_router.py`)
