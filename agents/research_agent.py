"""
Research Agent - Searches, summarizes, analyzes information using AI.
"""
from __future__ import annotations

from typing import Optional

import httpx

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.ai_providers import ai, AIMessage


class ResearchAgent(BaseAgent):
    name = "research"
    default_risk_level = RiskLevel.LOW

    SYSTEM_PROMPT = """You are the Research Agent of Dimentos AI Studio OS.
Analyze, summarize, and research topics thoroughly.
Provide structured, actionable insights. Be concise but complete."""

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "fetch" in task_lower or "scrape" in task_lower:
            return await self._fetch_url(params.get("url", ""))

        # Default: use AI to research/analyze/summarize
        return await self._ai_research(task, params)

    async def _ai_research(self, query: str, params: dict) -> ActionResult:
        self.logger.info(f"AI research: {query}")
        try:
            context = params.get("context", "")
            messages = []
            if context:
                messages.append(AIMessage(role="user", content=f"Context:\n{context}\n\nTask: {query}"))
            else:
                messages.append(AIMessage(role="user", content=query))

            response = await ai.chat_messages(
                messages=messages,
                system=self.SYSTEM_PROMPT,
                max_tokens=2048,
            )
            return ActionResult(success=True, data={
                "result": response.text,
                "provider": response.provider,
                "model": response.model,
                "tokens_out": response.output_tokens,
            })
        except Exception as e:
            self.logger.error(f"AI research failed: {e}")
            return ActionResult(success=False, error=str(e))

    async def _fetch_url(self, url: str) -> ActionResult:
        if not url:
            return ActionResult(success=False, error="URL required")
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                r = await client.get(url, timeout=15, headers={"User-Agent": "DimentosAI/1.0"})
                r.raise_for_status()
                content = r.text[:5000]
            return ActionResult(success=True, data={"url": url, "content": content, "length": len(r.text)})
        except Exception as e:
            return ActionResult(success=False, error=f"Failed to fetch {url}: {e}")
