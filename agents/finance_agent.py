"""
Finance Agent - Tracks costs, budgets, AI API expenses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx

from agents.base import BaseAgent, ActionResult, RiskLevel


class FinanceAgent(BaseAgent):
    """
    Finance Agent tracks all monetary transactions and AI usage costs.
    Reading is LOW risk. Recording expenses is LOW/MEDIUM.
    Payments always require HIGH approval.
    """

    name = "finance"
    default_risk_level = RiskLevel.LOW

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["pay", "transfer", "send money", "invoice"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["record", "log", "track"]):
            return RiskLevel.LOW
        return RiskLevel.LOW

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "usage" in task_lower or "cost" in task_lower or "summary" in task_lower:
            return await self._get_usage_summary()
        elif "log" in task_lower or "record" in task_lower:
            return await self._log_ai_usage(
                provider=params.get("provider", "unknown"),
                model=params.get("model", "unknown"),
                tokens=params.get("tokens", 0),
                cost=params.get("cost", 0.0),
            )
        elif "budget" in task_lower:
            return await self._get_budget_status()
        else:
            return await self._get_usage_summary()

    async def _get_usage_summary(self) -> ActionResult:
        """Fetch AI usage summary from the API."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.api_base_url}/api/finance/usage",
                timeout=10,
            )
            if r.status_code == 200:
                return ActionResult(success=True, data=r.json())
        return ActionResult(success=False, error="Could not fetch usage data")

    async def _log_ai_usage(
        self,
        provider: str,
        model: str,
        tokens: int,
        cost: float,
    ) -> ActionResult:
        """Log an AI API usage event."""
        self.logger.info(f"Logging AI usage: {provider}/{model} - {tokens} tokens - ${cost:.4f}")
        # In production: insert directly into DB or call API endpoint
        return ActionResult(
            success=True,
            data={
                "logged": True,
                "provider": provider,
                "model": model,
                "tokens": tokens,
                "cost_usd": cost,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def _get_budget_status(self) -> ActionResult:
        """Get current month budget status."""
        return ActionResult(
            success=True,
            data={
                "note": "Budget tracking - configure limits in .env",
                "current_month": datetime.now(timezone.utc).strftime("%Y-%m"),
                "status": "No budget limits configured",
            },
        )
