"""
Opportunity Analyst Agent — analyzes a project/job for fit, scores 0-100, calculates pricing.
Works on Opportunity records. Also doubles as Market Scout for manual URL submission.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal

import httpx
from loguru import logger
from sqlalchemy import select

from agents.base import BaseAgent, AgentResult
from core.ai_providers import ai
from core.database import AsyncSessionLocal
from core.models import Client, Opportunity

# Platform fee rates
PLATFORM_FEES = {
    "upwork": 20,
    "fiverr": 20,
    "freelancer": 10,
    "contra": 0,
    "peopleperhour": 20,
    "guru": 9,
    "direct": 0,
    "manual": 0,
}

# Service packages
PACKAGES = {
    "n8n_automation":    {"name": "n8n AI Automation",       "min": 150,  "max": 1500},
    "telegram_bot":      {"name": "Telegram Bot",             "min": 200,  "max": 1000},
    "ai_dashboard":      {"name": "AI Web Dashboard",         "min": 500,  "max": 3000},
    "claude_code":       {"name": "Claude Code Development",  "min": 300,  "max": 2000},
    "obsidian_memory":   {"name": "Obsidian AI Memory",       "min": 150,  "max": 800},
}

ANALYSIS_PROMPT = """Ты — AI-ассистент для фриланс-анализа проектов. Специализация исполнителя:
Python, FastAPI, Telegram-боты, n8n workflows, AI-интеграция (Claude/Gemini/OpenRouter),
автоматизация бизнеса, admin dashboards, CRM, парсинг, Linux/Windows администрирование,
PostgreSQL, Redis, Docker.

Анализируй этот проект по всем параметрам и верни JSON:

ПРОЕКТ:
Заголовок: {title}
Описание: {description}
Бюджет: {budget}
Источник: {source}

Верни ТОЛЬКО JSON (без markdown):
{{
  "score": <0-100, оценка соответствия>,
  "score_breakdown": {{
    "budget_fit": <0-20>,
    "skill_match": <0-30>,
    "clarity": <0-20>,
    "competition": <0-10>,
    "long_term": <0-10>,
    "risk": <0-10, 10=нет риска>
  }},
  "recommended": <true/false>,
  "recommended_package": <"n8n_automation"|"telegram_bot"|"ai_dashboard"|"claude_code"|"obsidian_memory"|"custom">,
  "budget_min": <число USD или null>,
  "budget_max": <число USD или null>,
  "estimated_hours": <число или null>,
  "pricing": {{
    "min": <минимальная цена USD>,
    "normal": <нормальная цена USD>,
    "premium": <премиум цена USD>
  }},
  "delivery_days": <число дней или null>,
  "platform_fee_pct": <комиссия платформы в %>,
  "summary": "<одна фраза: что делать и почему>",
  "key_requirements": ["требование1", "требование2"],
  "questions_for_client": ["вопрос1", "вопрос2"],
  "risk_flags": ["риск1"] или []
}}"""

PROPOSAL_PROMPT = """Напиши профессиональный отклик на проект. Ты — Zokir / Dimentos AI из Узбекистана.

ПРОЕКТ: {title}
ОПИСАНИЕ: {description}
БЮДЖЕТ: {budget}
АНАЛИЗ: {analysis}

НАШИ ПАКЕТЫ:
{packages}

Правила:
- Пиши на английском (для международных площадок) если проект на английском, иначе на русском
- Без шаблонных фраз типа "I hope this finds you well"
- Начни с понимания конкретной проблемы клиента
- Укажи похожий опыт (Telegram-боты, FastAPI, n8n, AI интеграция)
- Предложи конкретный план (2-3 шага)
- Укажи цену и сроки
- Задай 1-2 вопроса для уточнения
- Максимум 300 слов

Шаблон структуры (адаптируй, не копируй буквально):
Hello [Name if known / remove if unknown],

[Конкретная проблема которую решаю]

My experience with similar work:
[Конкретный опыт]

My approach:
1. [шаг]
2. [шаг]
3. [шаг]

Investment: $[price] | Delivery: [X] days

[1 уточняющий вопрос]

Best,
Zokir / Dimentos AI"""


class OpportunityAnalyst(BaseAgent):
    name = "analyst"

    async def execute(self, task: str = "", **kwargs) -> AgentResult:
        action = kwargs.get("action", "analyze")

        if action == "submit_url":
            return await self._submit_url(kwargs.get("url", task), kwargs.get("description", ""))
        elif action == "analyze":
            opp_id = kwargs.get("opportunity_id") or task
            return await self._analyze(opp_id)
        elif action == "propose":
            opp_id = kwargs.get("opportunity_id") or task
            return await self._generate_proposal(opp_id)
        elif action == "full_pipeline":
            # submit → analyze → propose → send approval to Telegram
            url = kwargs.get("url", task)
            desc = kwargs.get("description", "")
            return await self._full_pipeline(url, desc)
        return AgentResult(agent=self.name, action=action, result="Неизвестное действие", data={})

    async def _submit_url(self, url: str, description: str = "") -> AgentResult:
        """Accept a URL, scrape title/description if possible, save as Opportunity."""
        if not url:
            return AgentResult(agent=self.name, action="submit_url",
                               result="URL не указан", data={})

        title = f"Проект с {url[:50]}"
        fetched_desc = description

        # Try to fetch page and extract text
        if url.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        text = resp.text[:5000]
                        # Extract title
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', text, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()[:300]
                        if not fetched_desc:
                            # Very basic text extraction
                            clean = re.sub(r'<[^>]+>', ' ', text)
                            clean = re.sub(r'\s+', ' ', clean).strip()
                            fetched_desc = clean[:2000]
            except Exception as e:
                logger.warning(f"URL fetch failed: {e}")

        source = _detect_source(url)

        async with AsyncSessionLocal() as db:
            # Check duplicate
            existing = await db.execute(select(Opportunity).where(Opportunity.source_url == url))
            if existing.scalar_one_or_none():
                return AgentResult(agent=self.name, action="submit_url",
                                   result="Этот URL уже в базе", data={})

            opp = Opportunity(
                source=source,
                source_url=url,
                title=title[:500],
                description=fetched_desc or description,
                budget_raw="",
                status="NEW_FOUND",
                platform_fee_pct=PLATFORM_FEES.get(source, 20),
            )
            db.add(opp)
            await db.commit()
            opp_id = opp.id

        return AgentResult(
            agent=self.name, action="submit_url",
            result=f"Проект добавлен: {title[:60]}",
            data={"opportunity_id": opp_id, "title": title, "source": source},
        )

    async def _analyze(self, opportunity_id: str) -> AgentResult:
        """AI analysis and scoring of an opportunity."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Opportunity).where(Opportunity.id == opportunity_id))
            opp = res.scalar_one_or_none()
            if not opp:
                return AgentResult(agent=self.name, action="analyze",
                                   result="Opportunity не найден", data={})

            prompt = ANALYSIS_PROMPT.format(
                title=opp.title,
                description=(opp.description or "")[:1500],
                budget=opp.budget_raw or "не указан",
                source=opp.source,
            )

            try:
                response = await ai.chat(prompt, max_tokens=600)
                # Clean possible markdown
                clean = re.sub(r'```(?:json)?', '', response).strip()
                data = json.loads(clean)

                opp.score = data.get("score", 50)
                opp.score_breakdown = data.get("score_breakdown")
                opp.ai_analysis = data.get("summary", "")
                opp.budget_min_usd = data.get("budget_min")
                opp.budget_max_usd = data.get("budget_max")
                opp.estimated_hours = data.get("estimated_hours")
                opp.platform_fee_pct = data.get("platform_fee_pct", 20)
                opp.recommended_package = data.get("recommended_package")
                pricing = data.get("pricing", {})
                opp.pricing_min = pricing.get("min")
                opp.pricing_normal = pricing.get("normal")
                opp.pricing_premium = pricing.get("premium")
                opp.status = "ANALYZED" if float(opp.score) < 60 else "GOOD_FIT"
                await db.commit()

                rec = "✅ Рекомендован" if data.get("recommended") else "⚠️ Не рекомендован"
                return AgentResult(
                    agent=self.name, action="analyze",
                    result=f"Скор: {opp.score}/100 | {rec} | {opp.ai_analysis}",
                    data={**data, "opportunity_id": opportunity_id},
                )
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error in analyst: {e}\nResponse: {response[:200]}")
                return AgentResult(agent=self.name, action="analyze",
                                   result=f"Ошибка парсинга AI ответа: {e}", data={})
            except Exception as e:
                logger.error(f"Analyst error: {e}")
                return AgentResult(agent=self.name, action="analyze",
                                   result=f"Ошибка AI: {e}", data={})

    async def _generate_proposal(self, opportunity_id: str) -> AgentResult:
        """Generate a personalized proposal for an opportunity."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Opportunity).where(Opportunity.id == opportunity_id))
            opp = res.scalar_one_or_none()
            if not opp:
                return AgentResult(agent=self.name, action="propose",
                                   result="Opportunity не найден", data={})

            pkg = PACKAGES.get(opp.recommended_package or "", {})
            packages_text = "\n".join(
                f"- {v['name']}: ${v['min']}–${v['max']}" for v in PACKAGES.values()
            )

            prompt = PROPOSAL_PROMPT.format(
                title=opp.title,
                description=(opp.description or "")[:1000],
                budget=opp.budget_raw or f"${opp.pricing_normal or '?'}",
                analysis=opp.ai_analysis or "",
                packages=packages_text,
            )

            try:
                proposal_text = await ai.chat(prompt, max_tokens=700)

                from core.models import Proposal
                proposal = Proposal(
                    opportunity_id=opportunity_id,
                    content=proposal_text,
                    price_offered=opp.pricing_normal,
                    delivery_days=opp.estimated_hours // 8 if opp.estimated_hours else None,
                    status="draft",
                )
                db.add(proposal)
                opp.ai_proposal = proposal_text
                opp.status = "PROPOSAL_DRAFTED"
                await db.commit()
                proposal_id = proposal.id

                return AgentResult(
                    agent=self.name, action="propose",
                    result=proposal_text,
                    data={
                        "opportunity_id": opportunity_id,
                        "proposal_id": proposal_id,
                        "price": float(opp.pricing_normal) if opp.pricing_normal else None,
                    },
                )
            except Exception as e:
                logger.error(f"Proposal error: {e}")
                return AgentResult(agent=self.name, action="propose",
                                   result=f"Ошибка AI: {e}", data={})

    async def _full_pipeline(self, url: str, description: str = "") -> AgentResult:
        """Full pipeline: submit URL → analyze → generate proposal → send for approval."""
        # Step 1: submit
        submit_result = await self._submit_url(url, description)
        if "не" in submit_result.result.lower() and "найден" in submit_result.result.lower():
            return submit_result

        opp_id = submit_result.data.get("opportunity_id")
        if not opp_id:
            return submit_result

        # Step 2: analyze
        analyze_result = await self._analyze(opp_id)

        # Skip if score too low
        score = analyze_result.data.get("score", 0)
        if score < 40:
            return AgentResult(
                agent=self.name, action="full_pipeline",
                result=f"Проект отклонён (скор {score}/100): {analyze_result.result}",
                data={"opportunity_id": opp_id, "score": score, "action": "rejected"},
            )

        # Step 3: generate proposal
        propose_result = await self._generate_proposal(opp_id)

        # Step 4: send for Telegram approval
        await _send_opportunity_for_approval(opp_id, score, analyze_result, propose_result)

        return AgentResult(
            agent=self.name, action="full_pipeline",
            result=f"Готово! Скор {score}/100. Отклик отправлен в Telegram на подтверждение.",
            data={
                "opportunity_id": opp_id,
                "score": score,
                "proposal": propose_result.result[:500],
            },
        )


def _detect_source(url: str) -> str:
    url_lower = url.lower()
    for platform in ["upwork", "fiverr", "freelancer", "contra", "peopleperhour", "guru", "linkedin"]:
        if platform in url_lower:
            return platform
    return "manual"


async def _send_opportunity_for_approval(
    opp_id: str, score: float, analyze_result: AgentResult, propose_result: AgentResult
):
    """Send opportunity to Telegram approval flow via API."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                "http://localhost:8001/api/approvals/create",
                json={
                    "agent": "opportunity_analyst",
                    "action": "send_proposal",
                    "description": (
                        f"Отправить предложение?\n\n"
                        f"Скор: {score}/100\n"
                        f"Анализ: {analyze_result.result[:200]}\n\n"
                        f"Отклик:\n{propose_result.result[:400]}"
                    ),
                    "risk_level": "MEDIUM" if score >= 70 else "HIGH",
                    "payload": {"opportunity_id": opp_id},
                },
                timeout=10,
            )
    except Exception as e:
        logger.warning(f"Approval send failed: {e}")
