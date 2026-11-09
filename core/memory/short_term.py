"""
Short-Term Rolling Conversation Memory (Feature 7).
Maintains rolling window of conversation turns with automatic context summarization
to avoid context overflow while keeping critical recent dialogue verbatim.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ShortTermMemory:
    """Manages short-term conversation history with sliding-window summarization."""

    def __init__(self, max_turns: int = 15, keep_recent: int = 5):
        self.max_turns = max_turns
        self.keep_recent = keep_recent
        self._history: List[Dict[str, str]] = []
        self._context_summary: str = ""

    def add_message(self, role: str, content: str) -> None:
        """Appends a new turn and compresses older turns if limit exceeded."""
        self._history.append({
            "role": role,
            "content": content.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        if len(self._history) > self.max_turns:
            self._compress_older_turns()

    def _compress_older_turns(self) -> None:
        """Condenses older messages beyond keep_recent into a rolling summary."""
        if len(self._history) <= self.keep_recent:
            return

        split_idx = len(self._history) - self.keep_recent
        older = self._history[:split_idx]
        self._history = self._history[split_idx:]

        # Create compact summary points from older turns
        points = []
        for msg in older:
            role = msg["role"].capitalize()
            # Truncate content to 60 chars for concise summary
            snippet = msg["content"].replace("\n", " ")
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            points.append(f"{role}: {snippet}")

        incremental_summary = "; ".join(points)
        if self._context_summary:
            self._context_summary += f" | {incremental_summary}"
        else:
            self._context_summary = f"Earlier conversation context: {incremental_summary}"

        # Keep context summary within reasonable bounds (500 chars)
        if len(self._context_summary) > 500:
            self._context_summary = self._context_summary[-500:]

    def get_messages(self, include_summary: bool = True) -> List[Dict[str, str]]:
        """Returns messages ready for LLM consumption, optionally with summary."""
        messages: List[Dict[str, str]] = []

        if include_summary and self._context_summary:
            messages.append({
                "role": "system",
                "content": self._context_summary,
            })

        for msg in self._history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        return messages

    @property
    def summary(self) -> str:
        return self._context_summary

    def clear(self) -> None:
        """Clears short-term conversation buffer and summary."""
        self._history.clear()
        self._context_summary = ""

    def __len__(self) -> int:
        return len(self._history)


# Global short-term memory instance
short_term_memory = ShortTermMemory()
