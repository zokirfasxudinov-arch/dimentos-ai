"""
Dimentos AI Studio OS - Telegram Bot Main Entry Point
Owner-only bot with full approval flow and inline keyboards.
Token is loaded from environment, never hardcoded.
"""
from __future__ import annotations

import asyncio
import json
import sys

import redis.asyncio as aioredis
from loguru import logger
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from core.config import settings
from bot.handlers.commands import (
    cmd_start, cmd_status, cmd_tasks, cmd_agents,
    cmd_logs, cmd_projects, cmd_memory, cmd_github,
    cmd_settings, cmd_help, cmd_approve, cmd_reject, cmd_ai, cmd_task,
)
from bot.handlers.approvals import handle_approval_callback, send_approval_request
from bot.handlers.menu import handle_menu_callback
from bot.middleware import owner_only_middleware

APPROVAL_CHANNEL = "dimentos:approvals"


def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>bot</cyan> | {message}",
        level=settings.log_level,
    )
    logger.add(
        "/app/logs/bot.log",
        rotation="10 MB",
        retention="30 days",
        level="INFO",
    )


async def redis_approval_listener(app: Application):
    """Listen to Redis pub/sub for new approval requests and send Telegram notifications."""
    logger.info("Starting Redis approval listener...")
    while True:
        r = None
        pubsub = None
        try:
            r = aioredis.from_url(settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe(APPROVAL_CHANNEL)
            logger.info(f"Subscribed to Redis channel: {APPROVAL_CHANNEL}")

            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    logger.info(f"New approval from Redis: {data['approval_id'][:8]}")
                    await send_approval_request(
                        bot=app.bot,
                        approval_id=data["approval_id"],
                        agent=data["agent"],
                        action=data["action"],
                        description=data["description"],
                        risk_level=data["risk_level"],
                    )
                except Exception as e:
                    logger.error(f"Error processing approval notification: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(f"Redis listener error, reconnecting in 5s: {e}")
            await asyncio.sleep(5)
        finally:
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
                except Exception:
                    pass
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass


async def post_init(application: Application) -> None:
    """Runs after the bot starts."""
    commands = [
        ("start",    "Главное меню"),
        ("task",     "Поставить задачу агенту"),
        ("ai",       "Чат с AI"),
        ("approve",  "Подтвердить запрос"),
        ("status",   "Состояние системы"),
        ("tasks",    "Список задач"),
        ("agents",   "Статус агентов"),
        ("reject",   "Отклонить запрос"),
        ("logs",     "Логи"),
        ("projects", "Проекты"),
        ("memory",   "Память"),
        ("github",   "GitHub"),
        ("settings", "Настройки"),
        ("help",     "Помощь"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu configured")

    # Start Redis listener as background task
    asyncio.create_task(redis_approval_listener(application))
    logger.info("Redis approval listener started")


def main():
    setup_logging()

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set in .env!")
        sys.exit(1)

    logger.info("Starting Dimentos AI Studio OS Telegram Bot...")

    if not settings.telegram_owner_id:
        logger.warning("TELEGRAM_OWNER_ID not set — bot will reject all commands!")
    else:
        logger.info(f"Owner ID: {settings.telegram_owner_id}")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    def protected(handler):
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not await owner_only_middleware(update, context):
                return
            await handler(update, context)
        return wrapped

    app.add_handler(CommandHandler("start",    protected(cmd_start)))
    app.add_handler(CommandHandler("status",   protected(cmd_status)))
    app.add_handler(CommandHandler("tasks",    protected(cmd_tasks)))
    app.add_handler(CommandHandler("agents",   protected(cmd_agents)))
    app.add_handler(CommandHandler("approve",  protected(cmd_approve)))
    app.add_handler(CommandHandler("reject",   protected(cmd_reject)))
    app.add_handler(CommandHandler("logs",     protected(cmd_logs)))
    app.add_handler(CommandHandler("projects", protected(cmd_projects)))
    app.add_handler(CommandHandler("memory",   protected(cmd_memory)))
    app.add_handler(CommandHandler("github",   protected(cmd_github)))
    app.add_handler(CommandHandler("settings", protected(cmd_settings)))
    app.add_handler(CommandHandler("ai",       protected(cmd_ai)))
    app.add_handler(CommandHandler("task",     protected(cmd_task)))
    app.add_handler(CommandHandler("help",     protected(cmd_help)))

    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^approval:"))
    app.add_handler(CallbackQueryHandler(handle_menu_callback,     pattern=r"^menu:"))
    # Task/agent/github action callbacks (not needing approval flow)
    app.add_handler(CallbackQueryHandler(handle_menu_callback,     pattern=r"^(task:|agent:|github:)"))

    logger.info("Bot polling started. Waiting for messages...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
