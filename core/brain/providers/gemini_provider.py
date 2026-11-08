"""
Google Gemini Free Tier Provider.
Supports Gemini 2.0 Flash / 1.5 Flash with native function calling and streaming.
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from core.brain.base import BaseLLMProvider, ChatMessage, LLMResponse, ToolCallItem, ToolDefinition
from core.logger import logger


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self._api_key = api_key
        self._model = model
        self._client = None
        if self._api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        return bool(self._api_key and self._api_key.strip() and self._client)

    def _convert_tools(self, tools: Optional[List[ToolDefinition]]) -> Optional[List[Any]]:
        if not tools:
            return None
        from google.genai import types

        func_decls = []
        for t in tools:
            # Gemini expects JSON Schema in function declarations
            decl = types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.parameters,
            )
            func_decls.append(decl)
        return [types.Tool(function_declarations=func_decls)]

    def _format_contents_and_system(self, messages: List[ChatMessage]):
        system_instruction = None
        contents = []

        for m in messages:
            if m.role == "system":
                if system_instruction:
                    system_instruction += "\n" + m.content
                else:
                    system_instruction = m.content
            elif m.role == "user":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            elif m.role == "assistant":
                parts = []
                if m.content:
                    parts.append({"text": m.content})
                if m.tool_calls:
                    for tc in m.tool_calls:
                        parts.append({"function_call": tc})
                contents.append({"role": "model", "parts": parts})
            elif m.role == "tool":
                contents.append({
                    "role": "user",
                    "parts": [{
                        "function_response": {
                            "name": m.name or "tool_result",
                            "response": {"result": m.content}
                        }
                    }]
                })
        return system_instruction, contents

    async def generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if not self._client:
            raise RuntimeError("Gemini API key is not configured or client failed to initialize.")

        from google.genai import types

        start_time = time.perf_counter()
        system_instruction, contents = self._format_contents_and_system(messages)
        converted_tools = self._convert_tools(tools)

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
            tools=converted_tools,
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=contents,
            config=config,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        text_content = ""
        tool_calls: List[ToolCallItem] = []

        if response.candidates:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        text_content += part.text
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        fn_name = getattr(fc, "name", "")
                        fn_args = getattr(fc, "args", {})
                        if hasattr(fn_args, "items"):
                            fn_args = dict(fn_args)
                        tool_calls.append(
                            ToolCallItem(
                                id=f"call_{len(tool_calls)}_{int(time.time())}",
                                name=fn_name,
                                arguments=fn_args,
                            )
                        )

        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            provider=self.name,
            model=self._model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason="stop",
        )

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        if not self._client:
            raise RuntimeError("Gemini API key is not configured or client failed to initialize.")

        from google.genai import types

        system_instruction, contents = self._format_contents_and_system(messages)
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_instruction,
        )

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=config,
        )

        async for chunk in stream:
            if chunk.text:
                yield chunk.text
