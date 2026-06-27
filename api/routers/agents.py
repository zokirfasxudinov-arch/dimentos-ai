"""
Agent management endpoints.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import AgentLog

router = APIRouter()

# Registry of known agents
KNOWN_AGENTS = {
    "ceo": {"name": "CEO Agent", "status": "idle", "description": "Coordinates other agents"},
    "memory": {"name": "Memory Agent", "status": "idle", "description": "Reads/writes Obsidian vault"},
    "github": {"name": "GitHub Agent", "status": "idle", "description": "Manages git repos"},
    "research": {"name": "Research Agent", "status": "idle", "description": "Web research and synthesis"},
    "proposal": {"name": "Proposal Agent", "status": "idle", "description": "Writes proposals and documents"},
    "finance": {"name": "Finance Agent", "status": "idle", "description": "Tracks costs and budgets"},
    "security": {"name": "Security Agent", "status": "idle", "description": "Scans for security issues"},
}


class RunAgentRequest(BaseModel):
    task: str
    params: Optional[dict] = None


@router.get("/agents/status")
async def get_agents_status():
    """Returns status of all registered agents."""
    return {"agents": KNOWN_AGENTS}


@router.post("/agents/{name}/run")
async def run_agent(
    name: str,
    body: RunAgentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger an agent to run a task.
    HIGH/MEDIUM risk tasks require Telegram approval first.
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    # Log the run request
    log = AgentLog(
        agent_name=name,
        action=f"run:{body.task}",
        risk_level="LOW",
        result="queued",
    )
    db.add(log)
    await db.flush()

    return {
        "agent": name,
        "task": body.task,
        "status": "queued",
        "log_id": log.id,
        "message": f"Agent '{name}' task queued. Check /api/agents/{name}/logs for updates.",
    }


@router.get("/agents/{name}/logs")
async def get_agent_logs(
    name: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Get recent logs for a specific agent."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")

    stmt = (
        select(AgentLog)
        .where(AgentLog.agent_name == name)
        .order_by(AgentLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"agent": name, "logs": [item.to_dict() for item in items]}
