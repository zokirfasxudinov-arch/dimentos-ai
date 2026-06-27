"""
Dimentos AI Studio OS - SQLAlchemy Models
All database models are defined here.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Text, DateTime, Numeric, Integer,
    ForeignKey, JSON, func
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ApprovalRequest(Base):
    """Represents an agent action that requires human approval via Telegram."""
    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    risk_level = Column(String(20), nullable=False, default="MEDIUM")
    status = Column(String(20), nullable=False, default="pending")
    # pending | approved | rejected | deferred
    payload_json = Column(JSON, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(String(100), nullable=True)
    reason = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent,
            "action": self.action,
            "description": self.description,
            "risk_level": self.risk_level,
            "status": self.status,
            "payload_json": self.payload_json,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "decided_by": self.decided_by,
            "reason": self.reason,
        }


class AgentLog(Base):
    """Logs every action taken by an agent."""
    __tablename__ = "agent_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    agent_name = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    risk_level = Column(String(20), nullable=False, default="LOW")
    result = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_name": self.agent_name,
            "action": self.action,
            "risk_level": self.risk_level,
            "result": self.result,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class AuditLog(Base):
    """Full audit trail: who initiated, which agent, what action, who approved."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    initiator = Column(String(100), nullable=False)
    agent = Column(String(100), nullable=False)
    action = Column(String(255), nullable=False)
    risk_level = Column(String(20), nullable=False, default="LOW")
    approved_by = Column(String(100), nullable=True)
    result = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "initiator": self.initiator,
            "agent": self.agent,
            "action": self.action,
            "risk_level": self.risk_level,
            "approved_by": self.approved_by,
            "result": self.result,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class AIUsageLog(Base):
    """Tracks AI API usage and costs per provider."""
    __tablename__ = "ai_usage_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    tokens_used = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider": self.provider,
            "model": self.model,
            "tokens_used": self.tokens_used,
            "cost_usd": float(self.cost_usd),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Client(Base):
    """CRM: client / company."""
    __tablename__ = "clients"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(300), nullable=False)
    platform = Column(String(100), nullable=True)          # upwork, fiverr, direct, etc.
    platform_username = Column(String(200), nullable=True)
    email = Column(String(300), nullable=True)
    country = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    rating = Column(Numeric(3, 1), nullable=True)           # our rating of this client
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    opportunities = relationship("Opportunity", back_populates="client", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "platform": self.platform,
            "platform_username": self.platform_username, "email": self.email,
            "country": self.country, "notes": self.notes, "rating": float(self.rating) if self.rating else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


OPPORTUNITY_STATUSES = [
    "NEW_FOUND", "ANALYZED", "GOOD_FIT", "PROPOSAL_DRAFTED", "WAITING_APPROVAL",
    "PROPOSAL_SENT", "CLIENT_REPLIED", "NEGOTIATION", "ACCEPTED", "IN_PROGRESS",
    "QA", "DELIVERY_READY", "DELIVERED", "PAID", "REVIEW_REQUESTED",
    "CASE_STUDY_CREATED", "ARCHIVED",
]


class Opportunity(Base):
    """CRM: a potential project/job from any source."""
    __tablename__ = "opportunities"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    client_id = Column(UUID(as_uuid=False), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(100), nullable=False)            # upwork, fiverr, telegram, manual, etc.
    source_url = Column(String(1000), nullable=True, unique=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    budget_raw = Column(String(200), nullable=True)         # as stated on platform
    budget_min_usd = Column(Numeric(10, 2), nullable=True)
    budget_max_usd = Column(Numeric(10, 2), nullable=True)
    deadline_days = Column(Integer, nullable=True)
    platform_fee_pct = Column(Numeric(4, 1), nullable=True, default=20)  # e.g. 20% Upwork
    status = Column(String(50), nullable=False, default="NEW_FOUND")
    score = Column(Numeric(4, 1), nullable=True)            # 0-100
    score_breakdown = Column(JSON, nullable=True)           # detailed scoring
    ai_analysis = Column(Text, nullable=True)
    ai_proposal = Column(Text, nullable=True)
    pricing_min = Column(Numeric(10, 2), nullable=True)
    pricing_normal = Column(Numeric(10, 2), nullable=True)
    pricing_premium = Column(Numeric(10, 2), nullable=True)
    estimated_hours = Column(Integer, nullable=True)
    recommended_package = Column(String(100), nullable=True)  # n8n, telegram_bot, dashboard, etc.
    posted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    client = relationship("Client", back_populates="opportunities")
    proposals = relationship("Proposal", back_populates="opportunity", lazy="select")
    payments = relationship("Payment", back_populates="opportunity", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "client_id": self.client_id, "source": self.source,
            "source_url": self.source_url, "title": self.title,
            "description": self.description, "budget_raw": self.budget_raw,
            "budget_min_usd": float(self.budget_min_usd) if self.budget_min_usd else None,
            "budget_max_usd": float(self.budget_max_usd) if self.budget_max_usd else None,
            "platform_fee_pct": float(self.platform_fee_pct) if self.platform_fee_pct else 20,
            "status": self.status,
            "score": float(self.score) if self.score else None,
            "score_breakdown": self.score_breakdown,
            "ai_analysis": self.ai_analysis,
            "ai_proposal": self.ai_proposal,
            "pricing_min": float(self.pricing_min) if self.pricing_min else None,
            "pricing_normal": float(self.pricing_normal) if self.pricing_normal else None,
            "pricing_premium": float(self.pricing_premium) if self.pricing_premium else None,
            "estimated_hours": self.estimated_hours,
            "recommended_package": self.recommended_package,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Proposal(Base):
    """A drafted or sent proposal for an opportunity."""
    __tablename__ = "proposals"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    opportunity_id = Column(UUID(as_uuid=False), ForeignKey("opportunities.id", ondelete="CASCADE"))
    version = Column(Integer, nullable=False, default=1)
    content = Column(Text, nullable=False)
    price_offered = Column(Numeric(10, 2), nullable=True)
    delivery_days = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="draft")  # draft | approved | sent | rejected
    approved_by = Column(String(100), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    opportunity = relationship("Opportunity", back_populates="proposals")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "opportunity_id": self.opportunity_id,
            "version": self.version, "content": self.content,
            "price_offered": float(self.price_offered) if self.price_offered else None,
            "delivery_days": self.delivery_days, "status": self.status,
            "approved_by": self.approved_by,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Payment(Base):
    """Payments received for completed work."""
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    opportunity_id = Column(UUID(as_uuid=False), ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True)
    client_id = Column(UUID(as_uuid=False), ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    amount_gross = Column(Numeric(10, 2), nullable=False)   # before platform fee
    platform_fee = Column(Numeric(10, 2), nullable=True)
    amount_net = Column(Numeric(10, 2), nullable=True)      # after fee
    platform = Column(String(100), nullable=True)           # payoneer, upwork, etc.
    currency = Column(String(10), nullable=False, default="USD")
    status = Column(String(50), nullable=False, default="pending")  # pending | received | withdrawn
    paid_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    opportunity = relationship("Opportunity", back_populates="payments")

    def to_dict(self) -> dict:
        return {
            "id": self.id, "opportunity_id": self.opportunity_id,
            "client_id": self.client_id,
            "amount_gross": float(self.amount_gross),
            "platform_fee": float(self.platform_fee) if self.platform_fee else None,
            "amount_net": float(self.amount_net) if self.amount_net else None,
            "platform": self.platform, "currency": self.currency,
            "status": self.status,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Lead(Base):
    """Freelance job lead from job boards or manual entry."""
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    source = Column(String(100), nullable=False)        # fl.ru, freelance.ru, habr, manual
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True, unique=True)
    budget = Column(String(200), nullable=True)
    status = Column(String(50), nullable=False, default="new")
    # new | scored | proposal_ready | sent | negotiating | won | lost
    ai_score = Column(Numeric(3, 1), nullable=True)     # 1-10 fit score
    ai_analysis = Column(Text, nullable=True)            # why this score
    ai_proposal = Column(Text, nullable=True)            # generated proposal text
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "budget": self.budget,
            "status": self.status,
            "ai_score": float(self.ai_score) if self.ai_score else None,
            "ai_analysis": self.ai_analysis,
            "ai_proposal": self.ai_proposal,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EarningRecord(Base):
    """Track actual earnings from completed projects."""
    __tablename__ = "earning_records"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    lead_id = Column(UUID(as_uuid=False), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True)
    client = Column(String(255), nullable=False)
    service = Column(String(255), nullable=False)
    amount_usd = Column(Numeric(10, 2), nullable=False, default=0)
    amount_uzs = Column(Numeric(15, 0), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "client": self.client,
            "service": self.service,
            "amount_usd": float(self.amount_usd),
            "amount_uzs": int(self.amount_uzs) if self.amount_uzs else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Project(Base):
    """Project workspace."""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    tasks = relationship("Task", back_populates="project", lazy="select")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Task(Base):
    """Task within a project, assigned to an agent."""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    project_id = Column(UUID(as_uuid=False), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    agent = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    priority = Column(String(20), nullable=False, default="medium")
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    project = relationship("Project", back_populates="tasks")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "agent": self.agent,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
