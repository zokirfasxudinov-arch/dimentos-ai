"""
Opportunities API — full CRM for freelance pipeline management.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.models import Client, Opportunity, Proposal, Payment, OPPORTUNITY_STATUSES

router = APIRouter()

# ─── Clients ───────────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    name: str
    platform: Optional[str] = None
    platform_username: Optional[str] = None
    email: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


@router.get("/crm/clients")
async def list_clients(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Client).order_by(desc(Client.created_at)).limit(100))
    return {"clients": [c.to_dict() for c in res.scalars().all()]}


@router.post("/crm/clients")
async def create_client(body: ClientCreate, db: AsyncSession = Depends(get_db)):
    c = Client(**body.model_dump())
    db.add(c)
    await db.commit()
    return c.to_dict()


# ─── Opportunities ─────────────────────────────────────────────────────────


class OpportunityCreate(BaseModel):
    title: str
    source: str = "manual"
    source_url: Optional[str] = None
    description: Optional[str] = None
    budget_raw: Optional[str] = None


class UrlSubmit(BaseModel):
    url: str
    description: Optional[str] = None


class StatusUpdate(BaseModel):
    status: str


@router.post("/opportunities/submit")
async def submit_url(body: UrlSubmit):
    """Submit a URL for full AI analysis pipeline."""
    from agents.opportunity_analyst import OpportunityAnalyst
    agent = OpportunityAnalyst()
    result = await agent.execute(action="full_pipeline", url=body.url,
                                 description=body.description or "")
    return {"ok": True, "result": result.result, "data": result.data}


@router.post("/opportunities")
async def create_opportunity(body: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    opp = Opportunity(**body.model_dump())
    db.add(opp)
    await db.commit()
    return opp.to_dict()


@router.get("/opportunities")
async def list_opportunities(
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    q = select(Opportunity).order_by(desc(Opportunity.created_at)).limit(limit)
    if status:
        q = q.where(Opportunity.status == status)
    if min_score is not None:
        q = q.where(Opportunity.score >= min_score)
    res = await db.execute(q)
    opps = res.scalars().all()
    return {"opportunities": [o.to_dict() for o in opps], "count": len(opps)}


@router.get("/opportunities/stats")
async def opportunity_stats(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Opportunity.id)))).scalar()
    by_status = {}
    for s in OPPORTUNITY_STATUSES:
        cnt = (await db.execute(
            select(func.count(Opportunity.id)).where(Opportunity.status == s)
        )).scalar()
        if cnt:
            by_status[s] = cnt

    avg_score = (await db.execute(
        select(func.avg(Opportunity.score)).where(Opportunity.score.isnot(None))
    )).scalar()

    total_paid = (await db.execute(
        select(func.sum(Payment.amount_net)).where(Payment.status == "received")
    )).scalar() or 0

    total_pending = (await db.execute(
        select(func.sum(Payment.amount_gross)).where(Payment.status == "pending")
    )).scalar() or 0

    return {
        "total": total,
        "by_status": by_status,
        "avg_score": round(float(avg_score), 1) if avg_score else 0,
        "total_earned_usd": round(float(total_paid), 2),
        "total_pending_usd": round(float(total_pending), 2),
    }


@router.get("/opportunities/{opp_id}")
async def get_opportunity(opp_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
    opp = res.scalar_one_or_none()
    if not opp:
        raise HTTPException(404, "Not found")
    return opp.to_dict()


@router.put("/opportunities/{opp_id}/status")
async def update_status(opp_id: str, body: StatusUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Opportunity).where(Opportunity.id == opp_id))
    opp = res.scalar_one_or_none()
    if not opp:
        raise HTTPException(404, "Not found")
    if body.status not in OPPORTUNITY_STATUSES:
        raise HTTPException(400, f"Invalid status. Valid: {OPPORTUNITY_STATUSES}")
    opp.status = body.status
    await db.commit()
    return {"ok": True, "status": opp.status}


@router.post("/opportunities/{opp_id}/analyze")
async def analyze_opportunity(opp_id: str):
    """Run AI analysis on an existing opportunity."""
    from agents.opportunity_analyst import OpportunityAnalyst
    agent = OpportunityAnalyst()
    result = await agent.execute(action="analyze", opportunity_id=opp_id)
    return {"ok": True, "result": result.result, "data": result.data}


@router.post("/opportunities/{opp_id}/propose")
async def generate_proposal(opp_id: str):
    """Generate AI proposal for an opportunity."""
    from agents.opportunity_analyst import OpportunityAnalyst
    agent = OpportunityAnalyst()
    result = await agent.execute(action="propose", opportunity_id=opp_id)
    return {"ok": True, "proposal": result.result, "data": result.data}


# ─── Proposals ─────────────────────────────────────────────────────────────


@router.get("/opportunities/{opp_id}/proposals")
async def list_proposals(opp_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Proposal).where(Proposal.opportunity_id == opp_id)
        .order_by(desc(Proposal.created_at))
    )
    return {"proposals": [p.to_dict() for p in res.scalars().all()]}


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "Not found")
    p.status = "approved"
    p.approved_by = "telegram_owner"
    # Update parent opportunity status
    opp_res = await db.execute(select(Opportunity).where(Opportunity.id == p.opportunity_id))
    opp = opp_res.scalar_one_or_none()
    if opp:
        opp.status = "WAITING_APPROVAL"
    await db.commit()
    return {"ok": True, "status": "approved"}


# ─── Payments ──────────────────────────────────────────────────────────────


class PaymentCreate(BaseModel):
    opportunity_id: Optional[str] = None
    client_id: Optional[str] = None
    amount_gross: float
    platform: Optional[str] = None
    platform_fee_pct: Optional[float] = 20
    currency: str = "USD"
    notes: Optional[str] = None


@router.post("/payments")
async def record_payment(body: PaymentCreate, db: AsyncSession = Depends(get_db)):
    fee = body.amount_gross * (body.platform_fee_pct or 0) / 100
    net = body.amount_gross - fee
    p = Payment(
        opportunity_id=body.opportunity_id,
        client_id=body.client_id,
        amount_gross=body.amount_gross,
        platform_fee=fee,
        amount_net=net,
        platform=body.platform,
        currency=body.currency,
        notes=body.notes,
        status="pending",
    )
    db.add(p)
    # Update opportunity status if provided
    if body.opportunity_id:
        opp_res = await db.execute(select(Opportunity).where(Opportunity.id == body.opportunity_id))
        opp = opp_res.scalar_one_or_none()
        if opp:
            opp.status = "PAID"
    await db.commit()
    return p.to_dict()


@router.get("/payments")
async def list_payments(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Payment).order_by(desc(Payment.created_at)).limit(50))
    payments = res.scalars().all()
    total_net = sum(float(p.amount_net or 0) for p in payments)
    total_gross = sum(float(p.amount_gross) for p in payments)
    return {
        "payments": [p.to_dict() for p in payments],
        "total_gross": round(total_gross, 2),
        "total_net": round(total_net, 2),
    }
