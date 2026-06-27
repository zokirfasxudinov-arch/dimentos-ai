"""
CEO Agent - Coordinates other agents, plans tasks, oversees the studio.
"""
from __future__ import annotations

from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.ai_providers import ai


class CEOAgent(BaseAgent):
    """
    CEO Agent is the top-level coordinator.
    Breaks down goals into tasks and delegates to specialized agents.
    Uses AI to intelligently plan and route tasks.
    """

    name = "ceo"
    default_risk_level = RiskLevel.LOW

    TASK_ROUTING = {
        "memory": ["save", "recall", "note", "remember", "forget"],
        "github": ["commit", "push", "repo", "pull", "branch", "merge"],
        "research": ["research", "search", "find", "analyze", "summarize"],
        "proposal": ["proposal", "write", "draft", "document"],
        "finance": ["cost", "budget", "expense", "invoice", "payment"],
        "security": ["scan", "audit", "secret", "vulnerability", "risk"],
    }

    SYSTEM_PROMPT = """You are the CEO Agent of Dimentos AI Studio OS.
Your job is to plan tasks, delegate to specialized agents, and oversee execution.
Available agents: memory, github, research, proposal, finance, security.
Always respond in JSON with keys: agents (list), plan (list of steps), summary (string).
Be concise and practical."""

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        self.logger.info(f"CEO Agent planning: {task}")

        try:
            response = await ai.chat(
                prompt=f"Plan this task for the AI studio: {task}",
                system=self.SYSTEM_PROMPT,
                max_tokens=1024,
            )
            import json
            try:
                plan_data = json.loads(response.text)
            except Exception:
                plan_data = {
                    "agents": self._route_task(task),
                    "plan": self._create_plan(task, self._route_task(task)),
                    "summary": response.text[:300],
                }

            plan_data["ai_provider"] = response.provider
            plan_data["ai_model"] = response.model
            self.logger.info(f"AI plan via {response.provider}: {plan_data.get('summary', '')[:80]}")
            return ActionResult(success=True, data=plan_data)

        except Exception as e:
            self.logger.warning(f"AI planning failed, using static plan: {e}")
            involved = self._route_task(task)
            return ActionResult(success=True, data={
                "goal": task,
                "assigned_agents": involved,
                "plan": self._create_plan(task, involved),
                "status": "planned (no AI)",
            })

    def _route_task(self, task: str) -> list[str]:
        task_lower = task.lower()
        involved = [a for a, kws in self.TASK_ROUTING.items() if any(kw in task_lower for kw in kws)]
        return involved if involved else ["research"]

    def _create_plan(self, task: str, agents: list[str]) -> list[dict]:
        steps = []
        if "research" in agents:
            steps.append({"step": 1, "agent": "research", "action": f"Research: {task}", "risk": RiskLevel.LOW})
        for i, agent in enumerate((a for a in agents if a != "research"), start=2):
            steps.append({"step": i, "agent": agent, "action": f"Execute {agent}: {task}", "risk": RiskLevel.MEDIUM})
        steps.append({"step": len(steps) + 1, "agent": "memory", "action": "Save results", "risk": RiskLevel.LOW})
        return steps

    async def get_studio_status(self) -> dict:
        ai_status = ai.status()
        return {
            "agent": self.name,
            "status": "active",
            "available_agents": list(self.TASK_ROUTING.keys()),
            "ai_providers": ai_status,
        }
