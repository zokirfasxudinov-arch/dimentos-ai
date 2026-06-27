"""
CEO Agent - Coordinates other agents, plans tasks, oversees the studio.
"""
from __future__ import annotations

from typing import Optional

from loguru import logger

from agents.base import BaseAgent, ActionResult, RiskLevel


class CEOAgent(BaseAgent):
    """
    CEO Agent is the top-level coordinator.
    It breaks down goals into tasks and delegates to specialized agents.
    Never executes low-level actions directly.
    """

    name = "ceo"
    default_risk_level = RiskLevel.LOW  # Planning is safe; execution is delegated

    TASK_ROUTING = {
        "memory": ["save", "recall", "note", "remember", "forget"],
        "github": ["commit", "push", "repo", "pull", "branch", "merge"],
        "research": ["research", "search", "find", "analyze", "summarize"],
        "proposal": ["proposal", "write", "draft", "document"],
        "finance": ["cost", "budget", "expense", "invoice", "payment"],
        "security": ["scan", "audit", "secret", "vulnerability", "risk"],
    }

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        """
        CEO agent plans and delegates. Returns a delegation plan.
        """
        self.logger.info(f"CEO Agent planning: {task}")

        # Determine which agents to involve
        involved_agents = self._route_task(task)

        plan = {
            "goal": task,
            "assigned_agents": involved_agents,
            "steps": self._create_plan(task, involved_agents),
            "status": "planned",
        }

        self.logger.info(f"Plan created: {len(plan['steps'])} steps, agents: {involved_agents}")
        return ActionResult(success=True, data=plan)

    def _route_task(self, task: str) -> list[str]:
        """Determine which agents should handle a task."""
        task_lower = task.lower()
        involved = []
        for agent, keywords in self.TASK_ROUTING.items():
            if any(kw in task_lower for kw in keywords):
                involved.append(agent)
        return involved if involved else ["research"]  # Default to research agent

    def _create_plan(self, task: str, agents: list[str]) -> list[dict]:
        """Create a step-by-step execution plan."""
        steps = []
        step_num = 1

        if "research" in agents:
            steps.append({
                "step": step_num,
                "agent": "research",
                "action": f"Research context for: {task}",
                "risk": RiskLevel.LOW,
            })
            step_num += 1

        for agent in agents:
            if agent != "research":
                steps.append({
                    "step": step_num,
                    "agent": agent,
                    "action": f"Execute {agent} task: {task}",
                    "risk": RiskLevel.MEDIUM,
                })
                step_num += 1

        steps.append({
            "step": step_num,
            "agent": "memory",
            "action": "Save results to Obsidian vault",
            "risk": RiskLevel.LOW,
        })

        return steps

    async def get_studio_status(self) -> dict:
        """Get overall studio status."""
        return {
            "agent": self.name,
            "status": "active",
            "available_agents": list(self.TASK_ROUTING.keys()),
            "role": "Coordinator - delegates tasks to specialized agents",
        }
