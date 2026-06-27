"""
Proposal Agent - Writes proposals, TZs, client documents.
NEVER sends to external parties without explicit HIGH approval.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel


class ProposalAgent(BaseAgent):
    """
    Proposal Agent drafts documents.
    Drafting is LOW risk.
    Sending/publishing is always HIGH risk and requires approval.
    """

    name = "proposal"
    default_risk_level = RiskLevel.LOW

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["send", "email", "publish", "submit", "upload"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["finalize", "approve", "sign"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW  # drafting is safe

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "draft" in task_lower or "write" in task_lower or "create" in task_lower:
            return await self._draft_proposal(
                title=params.get("title", task),
                client=params.get("client", ""),
                requirements=params.get("requirements", ""),
                proposal_type=params.get("type", "general"),
            )
        elif "list" in task_lower:
            return await self._list_proposals()
        elif "send" in task_lower:
            return ActionResult(
                success=False,
                error="Sending requires explicit HIGH approval via Telegram first.",
            )
        else:
            return ActionResult(success=False, error=f"Unknown proposal task: {task}")

    async def _draft_proposal(
        self,
        title: str,
        client: str,
        requirements: str,
        proposal_type: str,
    ) -> ActionResult:
        """
        Generate a proposal draft and save to Obsidian vault.
        """
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d")

        proposal_content = f"""# {title}
**Date:** {timestamp}
**Client:** {client or "TBD"}
**Type:** {proposal_type}
**Status:** DRAFT - Not Sent

---

## Project Overview

{requirements or "Requirements to be filled in."}

---

## Scope of Work

- [ ] Requirement analysis
- [ ] Architecture design
- [ ] Implementation
- [ ] Testing & QA
- [ ] Deployment

---

## Timeline

| Phase | Duration |
|-------|----------|
| Analysis | 1 week |
| Design | 1 week |
| Implementation | 2-4 weeks |
| Testing | 1 week |
| Deployment | 3 days |

---

## Budget

*To be determined after requirements analysis.*

---

## Terms

- 50% upfront, 50% on delivery
- Source code delivered upon full payment
- 30-day bug fix warranty

---

> **DRAFT - Requires approval before sending**
> Use Telegram bot to approve and send.
"""

        # Save to vault
        safe_title = title.lower().replace(" ", "_").replace("/", "-")[:50]
        vault_path = Path("/app/obsidian-vault/12_TZ")
        vault_path.mkdir(parents=True, exist_ok=True)
        filename = f"{timestamp}_{safe_title}.md"
        (vault_path / filename).write_text(proposal_content, encoding="utf-8")

        self.logger.info(f"Proposal draft saved: {filename}")
        return ActionResult(
            success=True,
            data={
                "title": title,
                "path": f"12_TZ/{filename}",
                "status": "draft",
                "content": proposal_content,
                "note": "Draft saved. Requires approval before sending.",
            },
        )

    async def _list_proposals(self) -> ActionResult:
        vault_path = Path("/app/obsidian-vault/12_TZ")
        if not vault_path.exists():
            return ActionResult(success=True, data={"proposals": []})

        proposals = []
        for f in vault_path.glob("*.md"):
            proposals.append({
                "filename": f.name,
                "path": f"12_TZ/{f.name}",
                "size": f.stat().st_size,
            })

        return ActionResult(success=True, data={"proposals": proposals, "total": len(proposals)})
