"""
LLM Router with automatic multi-provider fallback.
Fallback chain: Ollama (Offline Local) -> Gemini Free -> Groq Free.
"""

from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional
from core.brain.base import BaseLLMProvider, ChatMessage, LLMResponse, ToolDefinition
from core.brain.providers import GeminiProvider, GroqProvider, OllamaProvider
from core.config import settings
from core.logger import logger


class LLMRouter:
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._system_prompt_cache: Optional[str] = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Instantiate providers based on settings."""
        self._providers["ollama"] = OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
        self._providers["gemini"] = GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )
        self._providers["groq"] = GroqProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )

    def get_system_prompt(self, reload: bool = False) -> str:
        """Reads and caches the system prompt from prompts/mike.md."""
        if self._system_prompt_cache is not None and not reload:
            return self._system_prompt_cache

        prompt_path = settings.system_prompt_path
        if prompt_path.exists():
            try:
                self._system_prompt_cache = prompt_path.read_text(encoding="utf-8")
                return self._system_prompt_cache
            except Exception as e:
                logger.error(f"Failed to read system prompt from {prompt_path}: {e}")

        # Fallback default prompt
        self._system_prompt_cache = (
            "You are MIKE, an autonomous agentic desktop assistant for Charan. "
            "Be warm, concise, and helpful. Always confirm sensitive actions."
        )
        return self._system_prompt_cache

    def get_provider(self, name: str) -> Optional[BaseLLMProvider]:
        return self._providers.get(name.lower())

    async def get_provider_status(self) -> Dict[str, Dict[str, Any]]:
        """Check availability status for all configured providers."""
        status = {}
        for name, provider in self._providers.items():
            avail = await provider.is_available()
            status[name] = {
                "available": avail,
                "model": provider.model_name,
                "is_primary": name == settings.llm_primary_provider.lower(),
            }
        return status

    async def _resolve_provider_chain(self, requested_provider: Optional[str] = None) -> List[BaseLLMProvider]:
        """Resolves the ordered list of providers to try."""
        chain_names: List[str] = []
        if requested_provider and requested_provider.lower() in self._providers:
            chain_names.append(requested_provider.lower())

        for p_name in settings.provider_chain:
            if p_name not in chain_names and p_name in self._providers:
                chain_names.append(p_name)

        return [self._providers[name] for name in chain_names]

    def _prepare_messages(self, messages: List[ChatMessage]) -> List[ChatMessage]:
        """Ensures the system prompt is present as the first message."""
        has_system = any(m.role == "system" for m in messages)
        if not has_system:
            system_prompt = self.get_system_prompt()
            return [ChatMessage(role="system", content=system_prompt)] + list(messages)
        return messages

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        provider_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """
        Executes generation across the fallback chain.
        Tries primary provider first, falling back automatically on error.
        """
        prepared_messages = self._prepare_messages(messages)
        chain = await self._resolve_provider_chain(provider_name)
        errors = []

        for provider in chain:
            if not await provider.is_available():
                logger.debug(f"Provider [{provider.name}] is not available/configured. Skipping.")
                continue

            try:
                logger.info(f"Attempting inference via [{provider.name}] (model: {provider.model_name})...")
                response = await provider.generate(
                    messages=prepared_messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                logger.info(
                    f"Inference succeeded via [{provider.name}] in {response.latency_ms:.1f}ms "
                    f"(Tokens: {response.prompt_tokens} in / {response.completion_tokens} out)"
                )
                return response
            except Exception as e:
                err_msg = f"Provider [{provider.name}] failed: {str(e)}"
                logger.warning(err_msg)
                errors.append(err_msg)

        # If all providers fail
        error_summary = " | ".join(errors) if errors else "No configured LLM providers were available."
        logger.error(f"All LLM providers in fallback chain failed: {error_summary}")
        raise RuntimeError(f"All LLM providers failed: {error_summary}")

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        provider_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Streams response tokens with fallback to next provider if streaming fails to start."""
        prepared_messages = self._prepare_messages(messages)
        chain = await self._resolve_provider_chain(provider_name)

        for provider in chain:
            if not await provider.is_available():
                continue
            try:
                logger.info(f"Streaming inference via [{provider.name}] (model: {provider.model_name})...")
                async for chunk in provider.stream_generate(
                    messages=prepared_messages,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    yield chunk
                return
            except Exception as e:
                logger.warning(f"Streaming from [{provider.name}] failed: {e}. Trying fallback...")

        raise RuntimeError("All LLM providers failed during streaming.")


# Global router instance
router = LLMRouter()
