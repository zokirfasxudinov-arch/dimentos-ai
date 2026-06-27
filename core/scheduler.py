"""
APScheduler — cron jobs for automatic lead search, scoring, weekly reports.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from loguru import logger

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={"coalesce": True, "max_instances": 1},
    timezone="Asia/Tashkent",
)


async def _job_search_leads():
    """Daily: search for new freelance leads."""
    logger.info("[Scheduler] Starting daily lead search...")
    try:
        from agents.lead_agent import LeadAgent
        agent = LeadAgent()
        result = await agent.execute(action="search")
        logger.info(f"[Scheduler] Lead search done: {result.result}")

        # Auto-score new leads after search
        await asyncio.sleep(2)
        await _job_score_new_leads()
    except Exception as e:
        logger.error(f"[Scheduler] Lead search error: {e}")


async def _job_score_new_leads():
    """Score all unscored leads with AI."""
    logger.info("[Scheduler] Scoring new leads...")
    try:
        from sqlalchemy import select
        from core.database import AsyncSessionLocal
        from core.models import Lead
        from agents.lead_agent import LeadAgent

        agent = LeadAgent()
        async with AsyncSessionLocal() as db:
            results = await db.execute(
                select(Lead).where(Lead.status == "new").limit(20)
            )
            leads = results.scalars().all()

        for lead in leads:
            await agent.execute(action="score", lead_id=str(lead.id))
            await asyncio.sleep(1)  # rate limit

        logger.info(f"[Scheduler] Scored {len(leads)} leads")
    except Exception as e:
        logger.error(f"[Scheduler] Scoring error: {e}")


async def _job_weekly_report():
    """Monday 8am: send weekly earnings + lead report to Telegram."""
    logger.info("[Scheduler] Generating weekly report...")
    try:
        from core.config import settings
        from core.database import AsyncSessionLocal
        from core.models import Lead, EarningRecord, AIUsageLog
        from sqlalchemy import select, func
        import httpx
        from datetime import timedelta

        week_ago = datetime.now() - timedelta(days=7)

        async with AsyncSessionLocal() as db:
            new_leads = (await db.execute(
                select(func.count(Lead.id)).where(Lead.created_at >= week_ago)
            )).scalar()
            won_leads = (await db.execute(
                select(func.count(Lead.id)).where(
                    Lead.status == "won", Lead.updated_at >= week_ago
                )
            )).scalar()
            ai_cost = (await db.execute(
                select(func.sum(AIUsageLog.cost_usd)).where(
                    AIUsageLog.timestamp >= week_ago
                )
            )).scalar() or 0

        text = (
            f"📊 <b>Еженедельный отчёт</b>\n\n"
            f"🔍 Найдено лидов: <b>{new_leads}</b>\n"
            f"🏆 Выиграно заказов: <b>{won_leads}</b>\n"
            f"💸 Расходы AI: <b>${float(ai_cost):.4f}</b>\n\n"
            f"Используй /leads чтобы посмотреть все лиды."
        )

        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": settings.telegram_owner_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
        logger.info("[Scheduler] Weekly report sent")
    except Exception as e:
        logger.error(f"[Scheduler] Weekly report error: {e}")


def setup_scheduler():
    """Register all cron jobs."""
    # Daily lead search at 9:00 AM Tashkent time
    scheduler.add_job(
        _job_search_leads,
        trigger="cron",
        hour=9,
        minute=0,
        id="daily_lead_search",
        replace_existing=True,
    )

    # Weekly report every Monday at 8:00 AM
    scheduler.add_job(
        _job_weekly_report,
        trigger="cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        id="weekly_report",
        replace_existing=True,
    )

    logger.info("Scheduler jobs registered: daily_lead_search (09:00), weekly_report (Mon 08:00)")
