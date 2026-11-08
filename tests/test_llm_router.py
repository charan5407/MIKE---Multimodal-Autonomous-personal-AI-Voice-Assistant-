"""
Unit tests for MIKE Core, Configuration, Logger, and LLM Router Fallback.
"""

import logging
from typing import AsyncIterator, List, Optional
import pytest

from core.brain.base import BaseLLMProvider, ChatMessage, LLMResponse, ToolDefinition
from core.brain.router import LLMRouter
from core.config import settings, Settings
from core.logger import SensitiveDataFilter


class MockFailingProvider(BaseLLMProvider):
    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return "llama3.1:8b"

    async def is_available(self) -> bool:
        return True

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        raise RuntimeError("Ollama daemon connection refused")

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        raise RuntimeError("Ollama stream error")
        yield ""  # generator syntax


class MockSucceedingProvider(BaseLLMProvider):
    def __init__(self):
        self.call_count = 0

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return "gemini-2.0-flash"

    async def is_available(self) -> bool:
        return True

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.call_count += 1
        return LLMResponse(
            content="Hello Charan, I am MIKE. System fallback worked perfectly.",
            provider=self.name,
            model=self.model_name,
            latency_ms=120.5,
            prompt_tokens=40,
            completion_tokens=15,
        )

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        yield "Hello "
        yield "Charan"


def test_settings_loading():
    s = Settings()
    assert s.app_name == "MIKE"
    assert s.owner_name == "Charan"
    assert len(s.provider_chain) >= 2
    assert s.prompts_dir.exists()
    assert s.system_prompt_path.exists()


def test_system_prompt_loading():
    router = LLMRouter()
    prompt = router.get_system_prompt()
    assert "MIKE" in prompt
    assert "Charan" in prompt
    assert "Rules" in prompt or "Guardrails" in prompt


def test_logger_redaction():
    exact_key = "AIzaSyDUMMYKEYFORTESTING1234567890"
    filter_instance = SensitiveDataFilter(exact_secrets=[exact_key])

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=f"Using key {exact_key} and phone +919876543210 with dob 2004-01-01",
        args=(),
        exc_info=None,
    )
    filter_instance.filter(record)

    assert exact_key not in record.msg
    assert "[REDACTED" in record.msg
    assert "2004-01-01" not in record.msg
    assert "+919876543210" not in record.msg


@pytest.mark.asyncio
async def test_router_fallback_mechanism():
    """Verify that router falls back to secondary provider if primary fails."""
    router = LLMRouter()
    mock_fail = MockFailingProvider()
    mock_success = MockSucceedingProvider()

    router._providers = {
        "ollama": mock_fail,
        "gemini": mock_success,
    }

    # Set provider chain order
    original_primary = settings.llm_primary_provider
    original_fallback = settings.llm_fallback_providers_raw
    try:
        settings.llm_primary_provider = "ollama"
        settings.llm_fallback_providers_raw = "gemini"

        response = await router.generate(
            messages=[ChatMessage(role="user", content="Hello Mike")]
        )

        assert response.provider == "gemini"
        assert "fallback worked" in response.content
        assert mock_success.call_count == 1
    finally:
        settings.llm_primary_provider = original_primary
        settings.llm_fallback_providers_raw = original_fallback


@pytest.mark.asyncio
async def test_router_stream_fallback():
    """Verify that router stream falls back if primary fails."""
    router = LLMRouter()
    mock_fail = MockFailingProvider()
    mock_success = MockSucceedingProvider()

    router._providers = {
        "ollama": mock_fail,
        "gemini": mock_success,
    }

    original_primary = settings.llm_primary_provider
    original_fallback = settings.llm_fallback_providers_raw
    try:
        settings.llm_primary_provider = "ollama"
        settings.llm_fallback_providers_raw = "gemini"

        collected = []
        async for chunk in router.stream_generate(
            messages=[ChatMessage(role="user", content="Hello Mike")]
        ):
            collected.append(chunk)

        assert "".join(collected) == "Hello Charan"
    finally:
        settings.llm_primary_provider = original_primary
        settings.llm_fallback_providers_raw = original_fallback


def test_tool_definition_serialization():
    tool = ToolDefinition(
        name="lock_workstation",
        description="Locks the Windows workstation.",
        parameters={"type": "object", "properties": {}},
    )
    assert tool.name == "lock_workstation"
    assert "properties" in tool.parameters
