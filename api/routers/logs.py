"""
Logs viewing endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import AgentLog, AuditLog

router = APIRouter()


@router.get("/logs/agent")
async def get_agent_logs(
    agent: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get agent action logs."""
    stmt = select(AgentLog)
    if agent:
        stmt = stmt.where(AgentLog.agent_name == agent)
    stmt = stmt.order_by(AgentLog.timestamp.desc()).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items], "total": len(items)}


@router.get("/logs/audit")
async def get_audit_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get full audit trail."""
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items], "total": len(items)}
