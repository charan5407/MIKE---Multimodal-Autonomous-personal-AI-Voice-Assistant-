"""
Groq Free Tier Provider for ultra-low latency inference and tool calling.
Uses the official AsyncGroq client.
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from core.brain.base import BaseLLMProvider, ChatMessage, LLMResponse, ToolCallItem, ToolDefinition
from core.logger import logger


class GroqProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self._api_key = api_key
        self._model = model
        self._client = None
        if self._api_key:
            try:
                from groq import AsyncGroq
                self._client = AsyncGroq(api_key=self._api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Groq client: {e}")

    @property
    def name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.strip() and self._client)

    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        converted = []
        for m in messages:
            msg: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            converted.append(msg)
        return converted

    def _convert_tools(self, tools: Optional[List[ToolDefinition]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Groq API key is not configured or client failed to initialize.")

        start_time = time.perf_counter()
        converted_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools)

        kwargs: Dict[str, Any] = {
            "model": self._model,
            "messages": converted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if converted_tools:
            kwargs["tools"] = converted_tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        latency_ms = (time.perf_counter() - start_time) * 1000

        choice = response.choices[0]
        msg = choice.message
        content = msg.content or ""

        tool_calls: List[ToolCallItem] = []
        if getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args_raw = tc.function.arguments
                try:
                    fn_args = json.loads(fn_args_raw)
                except Exception:
                    fn_args = {"raw": fn_args_raw}
                tool_calls.append(
                    ToolCallItem(
                        id=tc.id or f"call_{len(tool_calls)}_{int(time.time())}",
                        name=fn_name,
                        arguments=fn_args,
                    )
                )

        prompt_tokens = 0
        completion_tokens = 0
        if getattr(response, "usage", None):
            prompt_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(response.usage, "completion_tokens", 0) or 0

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            provider=self.name,
            model=self._model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=choice.finish_reason,
        )

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        if not self._client:
            raise RuntimeError("Groq API key is not configured or client failed to initialize.")

        converted_messages = self._convert_messages(messages)
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=converted_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

