"""
MIKE - Interactive CLI Chat & LLM Router Verification Interface.
Test prompt loading, provider fallback (Ollama -> Gemini -> Groq), latency, and tool-calling.
"""

import asyncio
import sys
from typing import List

from core.brain.base import ChatMessage, ToolDefinition
from core.brain.router import router
from core.config import settings
from core.logger import logger


BANNER = r"""
================================================================================
   __  __ _____ _  ________   - Multimodal Autonomous Agentic Desktop Assistant
  |  \/  |_   _| |/ /  ____|  - Owner: Charan (B.E./B.Tech AIML)
  | \  / | | | | ' /| |__     - Brain Router: Ollama (Offline) -> Gemini -> Groq
  | |\/| | | | |  < |  __|    - Status: Phase 1 Operational
  | |  | |_| |_| . \| |____  
  |_|  |_|_____|_|\_\______|  (Type /help for commands, /quit to exit)
================================================================================
"""

HELP_TEXT = """
Available Commands:
  /status             - Display live availability of Ollama, Gemini, and Groq
  /provider <name>    - Lock or test a specific provider (e.g. /provider gemini)
  /provider auto      - Reset back to automatic fallback chain
  /stream on|off      - Toggle token streaming (default: ON)
  /reload             - Reload prompts/mike.md without restarting
  /test-tools         - Verify native function/tool-calling on the active LLM
  /help               - Show this help message
  /quit or /exit      - Exit the CLI
"""


async def show_status():
    print("\n--- LLM Provider Status ---")
    status = await router.get_provider_status()
    for name, info in status.items():
        avail_str = "[ONLINE]" if info["available"] else "[OFFLINE / NO KEY]"
        primary_mark = " (PRIMARY)" if info["is_primary"] else ""
        print(f"  * {name.upper():<8} : {avail_str:<18} | Model: {info['model']}{primary_mark}")
    print(f"Active Provider Fallback Chain: {' -> '.join(settings.provider_chain)}")
    print("---------------------------\n")


async def test_tool_calling(selected_provider: str = None):
    print("\n[Tool Test] Testing native tool calling...")
    dummy_tool = ToolDefinition(
        name="get_weather",
        description="Get current weather for a given city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "The city name, e.g. Bangalore"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "default": "celsius"}
            },
            "required": ["city"]
        }
    )

    test_messages = [
        ChatMessage(role="user", content="Can you check the current weather in Bangalore for Charan?")
    ]

    try:
        response = await router.generate(
            messages=test_messages,
            tools=[dummy_tool],
            provider_name=selected_provider,
            temperature=0.2,
        )
        print(f"[Tool Test] Provider used: {response.provider} ({response.model}) in {response.latency_ms}ms")
        if response.tool_calls:
            print(f"[Tool Test] SUCCESS: Model triggered {len(response.tool_calls)} tool call(s):")
            for tc in response.tool_calls:
                print(f"   Function : {tc.name}")
                print(f"   Arguments: {tc.arguments}")
        else:
            print(f"[Tool Test] Model answered directly without calling tool: {response.content}")
    except Exception as e:
        print(f"[Tool Test] ERROR during tool calling test: {e}")
    print("-------------------------------------------\n")


async def main():
    print(BANNER)
    await show_status()

    conversation_history: List[ChatMessage] = []
    streaming_enabled = True
    active_provider = None

    while True:
        try:
            user_input = input("\nCharan > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["/quit", "/exit"]:
                print("\nMIKE: Goodbye Charan. Shutting down CLI session.")
                break

            if user_input.lower() == "/help":
                print(HELP_TEXT)
                continue

            if user_input.lower() == "/status":
                await show_status()
                continue

            if user_input.lower() == "/test-tools":
                await test_tool_calling(active_provider)
                continue

            if user_input.lower() == "/reload":
                prompt = router.get_system_prompt(reload=True)
                print(f"[MIKE] System prompt reloaded ({len(prompt)} characters).")
                continue

            if user_input.lower().startswith("/provider"):
                parts = user_input.split()
                if len(parts) > 1:
                    prov = parts[1].lower()
                    if prov == "auto":
                        active_provider = None
                        print("[MIKE] Switched to automatic provider fallback chain.")
                    elif prov in ["ollama", "gemini", "groq"]:
                        active_provider = prov
                        print(f"[MIKE] Locked inference provider to: {prov.upper()}")
                    else:
                        print("[MIKE] Unknown provider. Choose from: ollama, gemini, groq, auto")
                else:
                    current = active_provider or "auto (fallback chain)"
                    print(f"[MIKE] Current provider setting: {current}")
                continue

            if user_input.lower().startswith("/stream"):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].lower() in ["off", "false", "0"]:
                    streaming_enabled = False
                    print("[MIKE] Token streaming DISABLED.")
                else:
                    streaming_enabled = True
                    print("[MIKE] Token streaming ENABLED.")
                continue

            # Regular conversation flow
            conversation_history.append(ChatMessage(role="user", content=user_input))

            if streaming_enabled:
                print("MIKE > ", end="", flush=True)
                full_content = ""
                try:
                    async for chunk in router.stream_generate(
                        messages=conversation_history,
                        provider_name=active_provider,
                    ):
                        print(chunk, end="", flush=True)
                        full_content += chunk
                    print()  # newline
                    conversation_history.append(ChatMessage(role="assistant", content=full_content))
                except Exception as e:
                    print(f"\n[Error streaming response: {e}]")
            else:
                try:
                    response = await router.generate(
                        messages=conversation_history,
                        provider_name=active_provider,
                    )
                    print(f"\nMIKE > {response.content}")
                    print(f"[{response.provider} | {response.latency_ms:.0f}ms | {response.prompt_tokens}+{response.completion_tokens} tokens]")
                    conversation_history.append(ChatMessage(role="assistant", content=response.content))
                except Exception as e:
                    print(f"\n[Error generating response: {e}]")

        except (KeyboardInterrupt, EOFError):
            print("\n\nMIKE: Session interrupted. Exiting.")
            break


if __name__ == "__main__":
    asyncio.run(main())

