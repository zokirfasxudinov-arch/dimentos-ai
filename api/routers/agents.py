"""
Agent management endpoints — real execution, not just queuing.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import AgentLog

router = APIRouter()

KNOWN_AGENTS = {
    "ceo":      {"name": "CEO Agent",      "description": "Планирует задачи и делегирует агентам",     "icon": "🧠"},
    "research": {"name": "Research Agent", "description": "Исследует, анализирует, суммаризирует",     "icon": "🔍"},
    "proposal": {"name": "Proposal Agent", "description": "Пишет коммерческие предложения и ТЗ",       "icon": "📝"},
    "memory":   {"name": "Memory Agent",   "description": "Читает и записывает в Obsidian vault",       "icon": "🧩"},
    "github":   {"name": "GitHub Agent",   "description": "Управляет репозиториями и коммитами",        "icon": "🔗"},
    "finance":  {"name": "Finance Agent",  "description": "Отслеживает расходы и бюджет",               "icon": "💰"},
    "security": {"name": "Security Agent", "description": "Сканирует секреты и проверяет безопасность", "icon": "🔐"},
}


def _get_agent_instance(name: str):
    """Instantiate the agent class by name."""
    if name == "ceo":
        from agents.ceo_agent import CEOAgent
        return CEOAgent()
    elif name == "research":
        from agents.research_agent import ResearchAgent
        return ResearchAgent()
    elif name == "proposal":
        from agents.proposal_agent import ProposalAgent
        return ProposalAgent()
    elif name == "memory":
        from agents.memory_agent import MemoryAgent
        return MemoryAgent()
    elif name == "github":
        from agents.github_agent import GitHubAgent
        return GitHubAgent()
    elif name == "finance":
        from agents.finance_agent import FinanceAgent
        return FinanceAgent()
    elif name == "security":
        from agents.security_agent import SecurityAgent
        return SecurityAgent()
    return None


class RunAgentRequest(BaseModel):
    task: str
    params: Optional[dict] = None
    async_run: bool = False  # if True, run in background and return immediately


@router.get("/agents/status")
async def get_agents_status(db: AsyncSession = Depends(get_db)):
    """Returns status of all agents with their last activity."""
    result = await db.execute(
        select(AgentLog.agent_name, AgentLog.action, AgentLog.result, AgentLog.timestamp)
        .order_by(AgentLog.timestamp.desc())
        .limit(100)
    )
    rows = result.all()

    # Build last_run map
    last_run: dict[str, str] = {}
    for row in rows:
        if row.agent_name not in last_run:
            last_run[row.agent_name] = row.timestamp.strftime("%Y-%m-%d %H:%M") if row.timestamp else "?"

    agents_out = {}
    for key, info in KNOWN_AGENTS.items():
        agents_out[key] = {
            **info,
            "status": "idle",
            "last_run": last_run.get(key, "никогда"),
        }
    return {"agents": agents_out}


@router.post("/agents/{name}/run")
async def run_agent(
    name: str,
    body: RunAgentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Run an agent task. If async_run=True, returns immediately with log_id.
    Otherwise waits for result (up to 60s).
    """
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Агент '{name}' не найден")

    log_id = str(uuid4())
    log = AgentLog(
        id=log_id,
        agent_name=name,
        action=body.task[:200],
        risk_level="LOW",
        result="running",
        timestamp=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()

    if body.async_run:
        # Fire and forget
        background_tasks.add_task(_execute_agent_task, name, body.task, body.params, log_id)
        return {"agent": name, "task": body.task, "status": "started", "log_id": log_id}

    # Synchronous execution (wait for result)
    agent = _get_agent_instance(name)
    if not agent:
        raise HTTPException(status_code=500, detail=f"Не удалось создать агента '{name}'")

    try:
        result = await asyncio.wait_for(
            agent.execute(body.task, body.params),
            timeout=55,
        )
        outcome = "success" if result.success else f"error: {result.error}"
    except asyncio.TimeoutError:
        result_data = {"error": "timeout"}
        outcome = "timeout"
        return {"agent": name, "task": body.task, "status": "timeout", "log_id": log_id}
    except Exception as e:
        result_data = {"error": str(e)}
        outcome = f"exception: {e}"
        result = type("R", (), {"success": False, "data": None, "error": str(e)})()

    # Update log
    log.result = outcome[:200]
    await db.flush()

    return {
        "agent": name,
        "task": body.task,
        "status": "done" if result.success else "error",
        "success": result.success,
        "data": result.data,
        "error": result.error if not result.success else None,
        "log_id": log_id,
    }


async def _execute_agent_task(name: str, task: str, params: Optional[dict], log_id: str):
    """Background task execution — updates log when done."""
    from core.database import AsyncSessionLocal
    agent = _get_agent_instance(name)
    if not agent:
        return
    try:
        result = await asyncio.wait_for(agent.execute(task, params), timeout=120)
        outcome = "success" if result.success else f"error: {result.error}"
    except Exception as e:
        outcome = f"exception: {e}"

    async with AsyncSessionLocal() as db:
        log = await db.get(AgentLog, log_id)
        if log:
            log.result = outcome[:200]
            await db.commit()


@router.get("/agents/{name}/logs")
async def get_agent_logs(name: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get recent logs for a specific agent."""
    if name not in KNOWN_AGENTS:
        raise HTTPException(status_code=404, detail=f"Агент '{name}' не найден")
    stmt = (
        select(AgentLog)
        .where(AgentLog.agent_name == name)
        .order_by(AgentLog.timestamp.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return {"agent": name, "logs": [item.to_dict() for item in result.scalars().all()]}
