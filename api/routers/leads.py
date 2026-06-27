"""
Leads API — manage freelance leads, generate proposals, track earnings.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Lead, EarningRecord

router = APIRouter()


class LeadStatusUpdate(BaseModel):
    status: str


class EarningCreate(BaseModel):
    lead_id: Optional[str] = None
    client: str
    service: str
    amount_usd: float
    amount_uzs: Optional[int] = None
    notes: Optional[str] = None


@router.get("/leads")
async def list_leads(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(Lead).order_by(desc(Lead.created_at)).limit(limit)
    if status:
        q = q.where(Lead.status == status)
    if min_score is not None:
        q = q.where(Lead.ai_score >= min_score)
    results = await db.execute(q)
    leads = results.scalars().all()
    return {"leads": [l.to_dict() for l in leads], "count": len(leads)}


@router.get("/leads/stats")
async def lead_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Lead.id)))).scalar()
    by_status = {}
    for status in ["new", "scored", "proposal_ready", "sent", "negotiating", "won", "lost"]:
        cnt = (await db.execute(
            select(func.count(Lead.id)).where(Lead.status == status)
        )).scalar()
        by_status[status] = cnt

    avg_score = (await db.execute(
        select(func.avg(Lead.ai_score)).where(Lead.ai_score.isnot(None))
    )).scalar()

    total_earned = (await db.execute(
        select(func.sum(EarningRecord.amount_usd))
    )).scalar() or 0

    return {
        "total": total,
        "by_status": by_status,
        "avg_score": round(float(avg_score), 1) if avg_score else 0,
        "total_earned_usd": float(total_earned),
    }


@router.get("/leads/{lead_id}")
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead.to_dict()


@router.put("/leads/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    body: LeadStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.status = body.status
    await db.commit()
    return {"ok": True, "status": lead.status}


@router.post("/leads/{lead_id}/propose")
async def generate_proposal(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Generate AI proposal for a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(404, "Lead not found")

    from agents.outreach_agent import OutreachAgent
    agent = OutreachAgent()
    agent_result = await agent.execute(action="propose", lead_id=lead_id)
    return {"ok": True, "proposal": agent_result.result}


@router.post("/leads/search")
async def trigger_search():
    """Manually trigger lead search (runs in background)."""
    import asyncio
    from core.scheduler import _job_search_leads
    asyncio.create_task(_job_search_leads())
    return {"ok": True, "message": "Lead search started in background"}


@router.get("/earnings")
async def list_earnings(db: AsyncSession = Depends(get_db)):
    results = await db.execute(
        select(EarningRecord).order_by(desc(EarningRecord.created_at)).limit(50)
    )
    records = results.scalars().all()
    total = sum(float(r.amount_usd) for r in records)
    return {
        "earnings": [r.to_dict() for r in records],
        "total_usd": round(total, 2),
        "count": len(records),
    }


@router.post("/earnings")
async def add_earning(body: EarningCreate, db: AsyncSession = Depends(get_db)):
    record = EarningRecord(
        lead_id=body.lead_id,
        client=body.client,
        service=body.service,
        amount_usd=body.amount_usd,
        amount_uzs=body.amount_uzs,
        notes=body.notes,
    )
    db.add(record)
    await db.commit()
    return record.to_dict()
