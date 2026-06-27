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
