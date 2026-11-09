"""
Web Search Tool for MIKE.
Integrates DuckDuckGo via duckduckgo-search (100% free, zero API key).
Searches web queries, extracts snippets and URLs, and formats source citations.
Powers the desktop Voice Search Bar and knowledge retrieval.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.logger import logger
from core.security.permissions import PermissionTier
from core.tools.base import BaseTool, ToolResult
from core.tools.cancellation import CancellationToken


class WebSearchArgs(BaseModel):
    query: str = Field(..., description="The search query topic to look up on the web.")
    max_results: int = Field(default=5, description="Maximum number of search results to return (default 5).")


class WebSearchTool(BaseTool):
    """Searches the web using DuckDuckGo and formats structured results with sources."""

    name = "web_search"
    description = "Searches the web for current information, facts, or news using DuckDuckGo and returns titles, snippets, and source links."
    tier = PermissionTier.TIER_A_SAFE
    args_schema = WebSearchArgs
    timeout_sec = 15.0

    async def execute(
        self,
        cancellation_token: CancellationToken,
        query: str = "",
        max_results: int = 5,
        **kwargs: Any,
    ) -> ToolResult:
        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(success=False, error="Operation cancelled by user.")

        query = query.strip()
        if not query:
            return ToolResult(success=False, error="Search query cannot be empty.")

        logger.info(f"Executing web search for query: '{query}' (max_results: {max_results})")

        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=max_results))

            if not raw_results:
                return ToolResult(
                    success=True,
                    output=f"No web results found for query: '{query}'.",
                    data={"query": query, "results": []},
                )

            formatted_lines = [f"Web search results for '{query}':\n"]
            structured_data = []

            for i, r in enumerate(raw_results, 1):
                title = r.get("title", "No Title")
                body = r.get("body", "No Snippet")
                url = r.get("href", "")

                formatted_lines.append(f"{i}. **{title}**\n   {body}\n   Source: {url}\n")
                structured_data.append({
                    "title": title,
                    "snippet": body,
                    "url": url,
                })

            summary_text = "\n".join(formatted_lines)
            return ToolResult(
                success=True,
                output=summary_text,
                data={
                    "query": query,
                    "count": len(structured_data),
                    "results": structured_data,
                },
            )

        except Exception as e:
            logger.error(f"Web search error: {e}")
            return ToolResult(
                success=False,
                error=f"Web search failed: {e}. Please check internet connection.",
            )

