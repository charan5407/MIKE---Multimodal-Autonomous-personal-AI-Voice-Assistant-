"""
Base definitions and interfaces for LLM providers and message formatting.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: str = ""
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema format


class ToolCallItem(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    content: str = ""
    tool_calls: List[ToolCallItem] = Field(default_factory=list)
    provider: str
    model: str
    latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: Optional[str] = None


class BaseLLMProvider(ABC):
    """Abstract interface that all LLM providers (Ollama, Gemini, Groq) implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name identifier, e.g. 'ollama', 'gemini', 'groq'."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier currently configured."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Checks if the provider is reachable and credentials/host are valid."""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a complete response from the LLM, optionally handling native tool calling."""
        pass

    @abstractmethod
    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        """Stream chunks of text from the LLM."""
        pass

