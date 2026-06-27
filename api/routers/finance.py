"""
Finance tracking endpoints.
Tracks AI API usage costs and project expenses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import AIUsageLog

router = APIRouter()

# Approximate cost per 1M tokens (in USD)
COST_PER_1M = {
    "anthropic": {"in": 0.25, "out": 1.25},   # claude-haiku-4-5
    "openai":    {"in": 0.15, "out": 0.60},   # gpt-4o-mini
    "gemini":    {"in": 0.075, "out": 0.30},  # gemini-2.5-flash-lite
    "groq":      {"in": 0.05,  "out": 0.08},  # llama-3.3-70b
    "openrouter":{"in": 0.0,   "out": 0.0},   # free tier
}


class LogUsageRequest(BaseModel):
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


@router.post("/finance/log")
async def log_ai_usage(body: LogUsageRequest, db: AsyncSession = Depends(get_db)):
    """Log one AI API call with automatic cost calculation."""
    rates = COST_PER_1M.get(body.provider, {"in": 0.0, "out": 0.0})
    cost = (body.tokens_in * rates["in"] + body.tokens_out * rates["out"]) / 1_000_000

    log = AIUsageLog(
        id=str(uuid4()),
        provider=body.provider,
        model=body.model,
        tokens_used=body.tokens_in + body.tokens_out,
        cost_usd=cost,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()
    return {"logged": True, "cost_usd": cost}


@router.get("/finance/usage")
async def get_ai_usage(db: AsyncSession = Depends(get_db)):
    """Get AI usage summary grouped by provider."""
    stmt = (
        select(
            AIUsageLog.provider,
            AIUsageLog.model,
            func.sum(AIUsageLog.tokens_used).label("total_tokens"),
            func.sum(AIUsageLog.cost_usd).label("total_cost_usd"),
            func.count(AIUsageLog.id).label("call_count"),
        )
        .group_by(AIUsageLog.provider, AIUsageLog.model)
        .order_by(func.sum(AIUsageLog.cost_usd).desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    total_cost = sum(float(r.total_cost_usd or 0) for r in rows)

    return {
        "by_provider": [
            {
                "provider": r.provider,
                "model": r.model,
                "total_tokens": r.total_tokens,
                "total_cost_usd": float(r.total_cost_usd or 0),
                "call_count": r.call_count,
            }
            for r in rows
        ],
        "total_cost_usd": total_cost,
    }


@router.get("/finance/usage/history")
async def get_usage_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get recent AI usage log entries."""
    stmt = (
        select(AIUsageLog)
        .order_by(AIUsageLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items]}
