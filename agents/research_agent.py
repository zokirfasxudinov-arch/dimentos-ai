"""
Research Agent - Web research, data gathering, synthesis.
"""
from __future__ import annotations

from typing import Optional

import httpx

from agents.base import BaseAgent, ActionResult, RiskLevel


class ResearchAgent(BaseAgent):
    """
    Research Agent gathers information from the web.
    All research tasks are LOW risk (read-only).
    """

    name = "research"
    default_risk_level = RiskLevel.LOW

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "search" in task_lower or "find" in task_lower:
            return await self._web_search(params.get("query", task))
        elif "fetch" in task_lower or "scrape" in task_lower:
            return await self._fetch_url(params.get("url", ""))
        elif "summarize" in task_lower:
            return await self._summarize(params.get("text", ""))
        else:
            # Default: treat the task itself as a search query
            return await self._web_search(task)

    async def _web_search(self, query: str) -> ActionResult:
        """
        Search using a configured search API.
        Currently returns a structured placeholder - integrate with
        SerpAPI, Brave Search, Perplexity, etc. when API key is set.
        """
        self.logger.info(f"Searching: {query}")

        # Check for Perplexity API (best for research)
        from core.config import settings
        if settings.perplexity_api_key:
            return await self._search_perplexity(query, settings.perplexity_api_key)

        return ActionResult(
            success=True,
            data={
                "query": query,
                "results": [],
                "note": "No search API configured. Set PERPLEXITY_API_KEY in .env for web search.",
                "alternatives": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PERPLEXITY_API_KEY"],
            },
        )

    async def _search_perplexity(self, query: str, api_key: str) -> ActionResult:
        """Use Perplexity API for research."""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "llama-3.1-sonar-small-128k-online",
                    "messages": [
                        {"role": "user", "content": f"Research: {query}"}
                    ],
                    "max_tokens": 1024,
                },
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]

        return ActionResult(success=True, data={"query": query, "result": content, "provider": "perplexity"})

    async def _fetch_url(self, url: str) -> ActionResult:
        """Fetch content from a URL."""
        if not url:
            return ActionResult(success=False, error="URL required")

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(url, timeout=15, headers={"User-Agent": "DimentosAI/1.0"})
                r.raise_for_status()
                # Return first 5000 chars to avoid huge payloads
                content = r.text[:5000]
            return ActionResult(success=True, data={"url": url, "content": content, "length": len(r.text)})
        except Exception as e:
            return ActionResult(success=False, error=f"Failed to fetch {url}: {e}")

    async def _summarize(self, text: str) -> ActionResult:
        """Summarize text using an available AI provider."""
        if not text:
            return ActionResult(success=False, error="Text to summarize is required")

        from core.config import settings
        if not settings.available_providers:
            return ActionResult(
                success=False,
                error="No AI provider configured. Set an API key in .env to use summarization.",
            )

        # Use the first available provider
        # In production, implement actual AI calls here
        return ActionResult(
            success=True,
            data={
                "note": f"Summarization via {settings.available_providers[0]} - implement AI call here",
                "text_length": len(text),
            },
        )
