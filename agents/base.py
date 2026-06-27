"""
Dimentos AI Studio OS - Base Agent
All agents inherit from this class. Implements the approval flow.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from loguru import logger

from core.config import settings


class RiskLevel:
    LOW = "LOW"         # Auto-execute, no approval needed
    MEDIUM = "MEDIUM"   # Requires Telegram approval
    HIGH = "HIGH"       # Always requires approval, double-confirm


class ActionResult:
    def __init__(self, success: bool, data: Any = None, error: str = ""):
        self.success = success
        self.data = data
        self.error = error

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}


class BaseAgent(ABC):
    """
    Base class for all Dimentos AI agents.

    Risk levels:
    - LOW: auto-execute immediately
    - MEDIUM: create approval request, notify via Telegram
    - HIGH: create approval request, require explicit confirmation
    """

    name: str = "base"
    default_risk_level: str = RiskLevel.MEDIUM
    api_base_url: str = f"http://localhost:{settings.api_port}"

    def __init__(self):
        self.logger = logger.bind(agent=self.name)

    def can_execute_directly(self, risk_level: str) -> bool:
        """Returns True if the action can run without approval."""
        return risk_level == RiskLevel.LOW

    async def request_approval(
        self,
        action: str,
        description: str,
        risk_level: str = RiskLevel.MEDIUM,
        payload: Optional[dict] = None,
    ) -> str:
        """
        Submit an approval request to the API.
        Returns the approval request ID.
        """
        self.logger.info(f"Requesting approval for: {action} (risk={risk_level})")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base_url}/api/approvals/create",
                json={
                    "agent": self.name,
                    "action": action,
                    "description": description,
                    "risk_level": risk_level,
                    "payload_json": payload,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            approval_id = data["id"]

        self.logger.info(f"Approval request created: {approval_id}")
        return approval_id

    async def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> bool:
        """
        Poll the API until the approval is decided or timeout.
        Returns True if approved, False if rejected/timed out.
        """
        import asyncio
        elapsed = 0

        while elapsed < timeout_seconds:
            async with httpx.AsyncClient() as client:
                r = await client.get(
                    f"{self.api_base_url}/api/approvals/{approval_id}",
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    status = data.get("status")
                    if status == "approved":
                        self.logger.info(f"Approval {approval_id} granted")
                        return True
                    elif status in ("rejected", "deferred"):
                        self.logger.warning(f"Approval {approval_id} denied: {status}")
                        return False

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        self.logger.error(f"Approval {approval_id} timed out after {timeout_seconds}s")
        return False

    async def log_action(
        self,
        action: str,
        result: str,
        risk_level: str = RiskLevel.LOW,
    ) -> None:
        """Log an agent action to the API."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.api_base_url}/api/agents/{self.name}/run",
                    json={"task": action, "params": {"result": result, "risk_level": risk_level}},
                    timeout=5,
                )
        except Exception as e:
            self.logger.warning(f"Failed to log action: {e}")

    async def run(self, task: str, params: Optional[dict] = None) -> ActionResult:
        """
        Main entry point for running an agent task.
        Override this in subclasses.
        """
        risk_level = self.assess_risk(task, params)

        if not self.can_execute_directly(risk_level):
            approval_id = await self.request_approval(
                action=task,
                description=f"Agent '{self.name}' wants to execute: {task}",
                risk_level=risk_level,
                payload=params,
            )
            approved = await self.wait_for_approval(approval_id)
            if not approved:
                return ActionResult(success=False, error="Action not approved")

        return await self.execute(task, params)

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        """
        Assess the risk level of a task.
        Override in subclasses for smarter assessment.
        """
        return self.default_risk_level

    @abstractmethod
    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        """Execute the actual task. Called only after approval (if needed)."""
        ...
