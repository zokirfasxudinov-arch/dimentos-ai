"""
Finance tracking endpoints.
Tracks AI API usage costs and project expenses.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import AIUsageLog

router = APIRouter()


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
