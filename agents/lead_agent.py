"""
Lead Agent — searches freelance job boards, scores leads with AI, stores in DB.
Sources: fl.ru RSS, freelance.ru RSS, habr freelance RSS, weblancer RSS
"""
from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx
from loguru import logger
from sqlalchemy import select

from agents.base import BaseAgent, AgentResult
from core.ai_providers import ai
from core.database import AsyncSessionLocal
from core.models import Lead


# Skills we can sell — used for scoring
OUR_SKILLS = [
    "python", "telegram", "бот", "bot", "автоматизация", "automation",
    "ai", "ии", "chatgpt", "gpt", "claude", "нейросеть",
    "fastapi", "django", "flask", "api", "rest",
    "windows", "active directory", "ad", "powershell", "winrm",
    "linux", "ubuntu", "debian", "сервер", "server",
    "postgresql", "postgres", "mysql", "sqlite",
    "redis", "celery", "docker",
    "mikrotik", "сеть", "network", "vpn",
    "парсинг", "parser", "scraper", "скрапинг",
    "excel", "таблица", "spreadsheet",
]

# RSS feeds to check
FEEDS = [
    {
        "source": "fl.ru",
        "url": "https://www.fl.ru/rss/projects/",
        "category": "general",
    },
    {
        "source": "fl.ru/python",
        "url": "https://www.fl.ru/rss/projects/?tid=25",
        "category": "python",
    },
    {
        "source": "freelance.ru",
        "url": "https://freelance.ru/rss/projects/",
        "category": "general",
    },
    {
        "source": "habr.freelance",
        "url": "https://freelance.habr.com/tasks.rss",
        "category": "it",
    },
    {
        "source": "weblancer",
        "url": "https://www.weblancer.net/jobs/feed/",
        "category": "general",
    },
]

SCORE_PROMPT = """Ты — эксперт по фрилансу. Оцени этот заказ для исполнителя по навыкам:
Python, Telegram-боты, AI-интеграция, автоматизация, FastAPI, Linux/Windows-администрирование, PostgreSQL, Docker, парсинг, MikroTik/сети.

Заказ: {title}
Описание: {description}
Бюджет: {budget}

Ответь ТОЛЬКО в формате JSON:
{{
  "score": <число от 1 до 10>,
  "fit": "<одна фраза — почему подходит/не подходит>",
  "key_skills": ["навык1", "навык2"],
  "estimated_hours": <число или null>,
  "recommended": <true/false>
}}"""


def _url_id(url: str) -> str:
    """Stable unique ID from URL."""
    return hashlib.md5(url.encode()).hexdigest()[:20]


def _quick_score(title: str, description: str) -> float:
    """Fast keyword-based pre-score before AI scoring."""
    text = (title + " " + description).lower()
    matches = sum(1 for skill in OUR_SKILLS if skill in text)
    return min(10.0, matches * 1.5)


class LeadAgent(BaseAgent):
    name = "lead"

    async def execute(self, task: str = "", **kwargs) -> AgentResult:
        action = kwargs.get("action", "search")

        if action == "search":
            return await self._search_leads()
        elif action == "score":
            lead_id = kwargs.get("lead_id")
            return await self._score_lead(lead_id)
        elif action == "stats":
            return await self._get_stats()
        else:
            return await self._search_leads()

    async def _search_leads(self) -> AgentResult:
        """Fetch RSS feeds, find new leads, store in DB."""
        new_count = 0
        errors = []

        async with AsyncSessionLocal() as db:
            for feed_cfg in FEEDS:
                try:
                    entries = await self._fetch_feed(feed_cfg["url"])
                    for entry in entries[:20]:  # max 20 per feed
                        url = entry.get("link", "")
                        if not url:
                            continue

                        # Skip if already in DB
                        existing = await db.execute(
                            select(Lead).where(Lead.url == url)
                        )
                        if existing.scalar_one_or_none():
                            continue

                        title = entry.get("title", "Без названия")[:500]
                        desc = entry.get("summary", "")[:2000]
                        budget = entry.get("fl_cost", entry.get("price", ""))

                        quick = _quick_score(title, desc)
                        if quick < 1.5:  # skip clearly irrelevant
                            continue

                        lead = Lead(
                            source=feed_cfg["source"],
                            title=title,
                            description=desc,
                            url=url,
                            budget=str(budget) if budget else None,
                            status="new",
                        )
                        db.add(lead)
                        new_count += 1

                    await db.commit()
                except Exception as e:
                    errors.append(f"{feed_cfg['source']}: {e}")
                    logger.warning(f"Feed error {feed_cfg['source']}: {e}")

        result_text = f"Найдено новых лидов: {new_count}"
        if errors:
            result_text += f"\nОшибки ({len(errors)}): {'; '.join(errors[:3])}"

        return AgentResult(
            agent=self.name,
            action="search_leads",
            result=result_text,
            data={"new_leads": new_count, "errors": errors},
        )

    async def _fetch_feed(self, url: str) -> list[dict]:
        """Fetch and parse RSS feed asynchronously."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "DimentosAI/1.0"})
                if resp.status_code != 200:
                    return []
                parsed = feedparser.parse(resp.text)
                return [dict(e) for e in parsed.entries]
        except Exception as e:
            logger.warning(f"Feed fetch failed {url}: {e}")
            return []

    async def _score_lead(self, lead_id: Optional[str]) -> AgentResult:
        """Use AI to score a specific lead."""
        if not lead_id:
            return AgentResult(agent=self.name, action="score_lead",
                               result="lead_id required", data={})

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if not lead:
                return AgentResult(agent=self.name, action="score_lead",
                                   result="Lead not found", data={})

            prompt = SCORE_PROMPT.format(
                title=lead.title,
                description=(lead.description or "")[:500],
                budget=lead.budget or "не указан",
            )

            try:
                import json
                response = await ai.chat(prompt, max_tokens=300)
                data = json.loads(response.strip())
                lead.ai_score = data.get("score", 5)
                lead.ai_analysis = data.get("fit", "")
                lead.status = "scored"
                await db.commit()
                return AgentResult(
                    agent=self.name,
                    action="score_lead",
                    result=f"Оценка: {data['score']}/10 — {data.get('fit','')}",
                    data=data,
                )
            except Exception as e:
                logger.error(f"AI scoring failed: {e}")
                return AgentResult(agent=self.name, action="score_lead",
                                   result=f"Ошибка AI: {e}", data={})

    async def _get_stats(self) -> AgentResult:
        """Return lead statistics."""
        from sqlalchemy import func as sqlfunc
        async with AsyncSessionLocal() as db:
            total = (await db.execute(select(sqlfunc.count(Lead.id)))).scalar()
            new = (await db.execute(
                select(sqlfunc.count(Lead.id)).where(Lead.status == "new")
            )).scalar()
            won = (await db.execute(
                select(sqlfunc.count(Lead.id)).where(Lead.status == "won")
            )).scalar()

        return AgentResult(
            agent=self.name,
            action="stats",
            result=f"Лидов всего: {total}, новых: {new}, выиграно: {won}",
            data={"total": total, "new": new, "won": won},
        )
