"""
Outreach Agent — generates personalized proposals for freelance leads.
Uses AI to write a compelling response in Russian, tailored to the job.
"""
from __future__ import annotations

from loguru import logger
from sqlalchemy import select

from agents.base import BaseAgent, AgentResult
from core.ai_providers import ai
from core.database import AsyncSessionLocal
from core.models import Lead


PROPOSAL_PROMPT = """Ты — опытный фрилансер из Узбекистана. Напиши отклик на этот заказ.

Заказ: {title}
Описание заказчика: {description}
Бюджет: {budget}
Источник: {source}

МОИ НАВЫКИ:
- Python, FastAPI, Telegram-боты (написал несколько рабочих ботов включая систему управления сетью)
- AI-интеграция (Anthropic Claude, Gemini, OpenRouter)
- Автоматизация (скрипты, парсинг, Windows/Linux администрирование)
- PostgreSQL, Redis, Docker, Nginx
- Windows Active Directory, PowerShell, WinRM (администрирование 60+ машин)
- MikroTik сети, Hikvision камеры

ТРЕБОВАНИЯ К ОТКЛИКУ:
- Коротко и по делу (3-5 абзацев)
- Начни с понимания задачи заказчика
- Укажи конкретный похожий опыт
- Предложи сроки и примерный план
- Закончи призывом к диалогу
- Тон: профессиональный, уверенный, без шаблонных фраз
- Язык: русский

Напиши только текст отклика, без пояснений."""


class OutreachAgent(BaseAgent):
    name = "outreach"

    async def execute(self, task: str = "", **kwargs) -> AgentResult:
        action = kwargs.get("action", "propose")

        if action == "propose":
            lead_id = kwargs.get("lead_id") or task
            return await self._generate_proposal(lead_id)
        elif action == "bulk_propose":
            return await self._bulk_propose(kwargs.get("min_score", 7.0))
        return AgentResult(agent=self.name, action=action,
                           result="Неизвестное действие", data={})

    async def _generate_proposal(self, lead_id: str) -> AgentResult:
        """Generate AI proposal for a specific lead."""
        if not lead_id:
            return AgentResult(agent=self.name, action="propose",
                               result="lead_id обязателен", data={})

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if not lead:
                return AgentResult(agent=self.name, action="propose",
                                   result="Лид не найден", data={})

            prompt = PROPOSAL_PROMPT.format(
                title=lead.title,
                description=(lead.description or "")[:800],
                budget=lead.budget or "не указан",
                source=lead.source,
            )

            try:
                proposal = await ai.chat(prompt, max_tokens=600)
                lead.ai_proposal = proposal
                lead.status = "proposal_ready"
                await db.commit()
                return AgentResult(
                    agent=self.name,
                    action="propose",
                    result=proposal,
                    data={"lead_id": lead_id, "lead_title": lead.title},
                )
            except Exception as e:
                logger.error(f"Proposal generation failed: {e}")
                return AgentResult(agent=self.name, action="propose",
                                   result=f"Ошибка AI: {e}", data={})

    async def _bulk_propose(self, min_score: float = 7.0) -> AgentResult:
        """Generate proposals for all high-scoring leads without proposals."""
        async with AsyncSessionLocal() as db:
            results = await db.execute(
                select(Lead).where(
                    Lead.ai_score >= min_score,
                    Lead.ai_proposal.is_(None),
                    Lead.status == "scored",
                )
            )
            leads = results.scalars().all()

        count = 0
        for lead in leads:
            result = await self._generate_proposal(str(lead.id))
            if "Ошибка" not in result.result:
                count += 1

        return AgentResult(
            agent=self.name,
            action="bulk_propose",
            result=f"Сгенерировано откликов: {count} из {len(leads)} подходящих лидов",
            data={"generated": count, "total_eligible": len(leads)},
        )
