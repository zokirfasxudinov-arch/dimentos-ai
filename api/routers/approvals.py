"""
Approval flow endpoints.
Agents submit actions here; the owner approves/rejects via Telegram or this API.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.models import ApprovalRequest

router = APIRouter()

APPROVAL_CHANNEL = "dimentos:approvals"


async def _notify_bot(approval_id: str, agent: str, action: str, description: str, risk_level: str):
    """Publish approval event to Redis so the bot can send a Telegram notification."""
    try:
        r = aioredis.from_url(settings.redis_url)
        payload = json.dumps({
            "approval_id": approval_id,
            "agent": agent,
            "action": action,
            "description": description,
            "risk_level": risk_level,
        })
        await r.publish(APPROVAL_CHANNEL, payload)
        await r.aclose()
        logger.info(f"Published approval {approval_id} to Redis channel")
    except Exception as e:
        logger.warning(f"Failed to publish approval to Redis: {e}")


class CreateApprovalRequest(BaseModel):
    agent: str
    action: str
    description: str
    risk_level: str = "MEDIUM"
    payload_json: Optional[dict] = None


class DecisionRequest(BaseModel):
    decided_by: str = "api"
    reason: Optional[str] = None


@router.get("/approvals")
async def list_approvals(
    status: Optional[str] = "pending",
    db: AsyncSession = Depends(get_db),
):
    """List approval requests, filtered by status."""
    stmt = select(ApprovalRequest)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    stmt = stmt.order_by(ApprovalRequest.requested_at.desc()).limit(100)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [item.to_dict() for item in items], "total": len(items)}


@router.post("/approvals/create")
async def create_approval(
    body: CreateApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new approval request (called by agents)."""
    req = ApprovalRequest(
        id=str(uuid4()),
        agent=body.agent,
        action=body.action,
        description=body.description,
        risk_level=body.risk_level,
        status="pending",
        payload_json=body.payload_json,
        requested_at=datetime.now(timezone.utc),
    )
    db.add(req)
    await db.flush()

    await _notify_bot(req.id, body.agent, body.action, body.description, body.risk_level)

    return {"id": req.id, "status": "pending", "message": "Approval request created"}


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific approval request by ID."""
    req = await db.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return req.to_dict()


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Approve an action. Sets status to 'approved'."""
    req = await db.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already '{req.status}'")

    req.status = "approved"
    req.decided_at = datetime.now(timezone.utc)
    req.decided_by = body.decided_by
    req.reason = body.reason
    await db.flush()
    return {"id": req.id, "status": "approved"}


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    body: DecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject an action. Sets status to 'rejected'."""
    req = await db.get(ApprovalRequest, approval_id)
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already '{req.status}'")

    req.status = "rejected"
    req.decided_at = datetime.now(timezone.utc)
    req.decided_by = body.decided_by
    req.reason = body.reason
    await db.flush()
    return {"id": req.id, "status": "rejected"}
