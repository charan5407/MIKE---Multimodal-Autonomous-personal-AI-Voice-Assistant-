"""
Ollama Local LLM Provider for offline use.
Communicates directly with the Ollama REST API (default: http://localhost:11434).
"""

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional
import httpx

from core.brain.base import BaseLLMProvider, ChatMessage, LLMResponse, ToolCallItem, ToolDefinition
from core.logger import logger


class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self._base_url = base_url.rstrip("/")
        self._model = model

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    async def is_available(self) -> bool:
        """Ping Ollama API to see if the daemon is running and has access."""
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                res = await client.get(f"{self._base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def _convert_messages(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        converted = []
        for m in messages:
            msg_dict: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg_dict["tool_calls"] = m.tool_calls
            converted.append(msg_dict)
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
        start_time = time.perf_counter()
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        converted_tools = self._convert_tools(tools)
        if converted_tools:
            payload["tools"] = converted_tools

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.perf_counter() - start_time) * 1000
        msg = data.get("message", {})
        content = msg.get("content", "") or ""

        tool_calls: List[ToolCallItem] = []
        raw_tool_calls = msg.get("tool_calls", [])
        for idx, tc in enumerate(raw_tool_calls):
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            tool_calls.append(
                ToolCallItem(
                    id=f"call_{idx}_{int(time.time())}",
                    name=name,
                    arguments=args,
                )
            )

        prompt_eval = data.get("prompt_eval_count", 0) or 0
        eval_count = data.get("eval_count", 0) or 0

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            provider=self.name,
            model=self._model,
            latency_ms=round(latency_ms, 2),
            prompt_tokens=prompt_eval,
            completion_tokens=eval_count,
            finish_reason=data.get("done_reason", "stop"),
        )

    async def stream_generate(
        self,
        messages: List[ChatMessage],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", f"{self._base_url}/api/chat", json=payload) as stream:
                async for line in stream.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                    except Exception as e:
                        logger.debug(f"Error parsing Ollama stream chunk: {e}")
