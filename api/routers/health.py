"""
Health check endpoints.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter
from loguru import logger

from core.config import settings
from core.database import check_db_health

router = APIRouter()


@router.get("/health")
async def health_check():
    """Returns overall health status including DB and Redis connectivity."""
    db_ok = False
    redis_ok = False

    try:
        db_ok = await check_db_health()
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")

    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")

    overall = "ok" if (db_ok and redis_ok) else "degraded"

    return {
        "status": overall,
        "services": {
            "db": "ok" if db_ok else "unavailable",
            "redis": "ok" if redis_ok else "unavailable",
        },
        "version": "1.0.0",
    }
