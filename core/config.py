"""
MIKE Configuration Management.
Loads environment variables and defaults using Pydantic Settings.
"""

from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    app_name: str = "MIKE"
    app_version: str = "0.1.0"
    owner_name: str = "Charan"
    mike_env: str = Field(default="development", alias="MIKE_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Paths
    base_dir: Path = BASE_DIR
    prompts_dir: Path = BASE_DIR / "prompts"
    data_dir: Path = BASE_DIR / "data"
    logs_dir: Path = BASE_DIR / "logs"
    models_dir: Path = BASE_DIR / "models"
    system_prompt_path: Path = BASE_DIR / "prompts" / "mike.md"
    profile_path: Path = BASE_DIR / "data" / "profile.local.json"
    profile_example_path: Path = BASE_DIR / "data" / "profile.example.json"
    secret_key_path: Path = BASE_DIR / "data" / "secret_key.key"
    memory_db_path: Path = BASE_DIR / "data" / "memory.db"
    contacts_path: Path = BASE_DIR / "data" / "contacts.local.json"
    contacts_example_path: Path = BASE_DIR / "data" / "contacts.example.json"

    # LLM Router & Providers
    llm_primary_provider: str = Field(default="ollama", alias="LLM_PRIMARY_PROVIDER")
    llm_fallback_providers_raw: str = Field(default="gemini,groq", alias="LLM_FALLBACK_PROVIDERS")
    
    # 1. Ollama (Offline Local LLM)
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")

    # 2. Google Gemini Free Tier
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")

    # 3. Groq Free Tier
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # Security
    profile_encryption_key: Optional[str] = Field(default=None, alias="PROFILE_ENCRYPTION_KEY")

    # Spotify Integration
    spotify_client_id: Optional[str] = Field(default=None, alias="SPOTIFY_CLIENT_ID")
    spotify_client_secret: Optional[str] = Field(default=None, alias="SPOTIFY_CLIENT_SECRET")
    spotify_redirect_uri: str = Field(default="http://localhost:8888/callback", alias="SPOTIFY_REDIRECT_URI")

    # FastAPI & WebSocket Server
    server_host: str = Field(default="127.0.0.1", alias="SERVER_HOST")
    server_port: int = Field(default=8765, alias="SERVER_PORT")

    @property
    def fallback_providers(self) -> List[str]:
        if not self.llm_fallback_providers_raw:
            return []
        return [p.strip().lower() for p in self.llm_fallback_providers_raw.split(",") if p.strip()]

    @property
    def provider_chain(self) -> List[str]:
        chain = [self.llm_primary_provider.lower()]
        for p in self.fallback_providers:
            if p not in chain:
                chain.append(p)
        return chain


# Global cached settings instance
settings = Settings()

