"""
Dimentos AI Studio OS - Telegram Bot Main Entry Point
Owner-only bot with full approval flow and inline keyboards.
Token is loaded from environment, never hardcoded.
"""
from __future__ import annotations

import asyncio
import os
import sys

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
    cmd_start,
    cmd_status,
    cmd_tasks,
    cmd_agents,
    cmd_logs,
    cmd_projects,
    cmd_memory,
    cmd_github,
    cmd_settings,
    cmd_help,
    cmd_approve,
    cmd_reject,
)
from bot.handlers.approvals import handle_approval_callback
from bot.middleware import owner_only_middleware


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


async def post_init(application: Application) -> None:
    """Runs after the bot starts - set up bot commands menu."""
    commands = [
        ("start", "Start the bot"),
        ("status", "System status"),
        ("tasks", "List tasks"),
        ("agents", "Agent statuses"),
        ("approve", "Approve pending request"),
        ("reject", "Reject pending request"),
        ("logs", "Recent logs"),
        ("projects", "List projects"),
        ("memory", "Vault memory"),
        ("github", "GitHub status"),
        ("settings", "Bot settings"),
        ("help", "Show help"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu configured")


def main():
    setup_logging()

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set in .env!")
        sys.exit(1)

    logger.info("Starting Dimentos AI Studio OS Telegram Bot...")

    if not settings.telegram_owner_id:
        logger.warning("TELEGRAM_OWNER_ID not set - bot will reject all commands!")

    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(post_init)
        .build()
    )

    # Owner-only middleware wrapper
    def protected(handler):
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if not await owner_only_middleware(update, context):
                return
            await handler(update, context)
        return wrapped

    # Register command handlers (all owner-only)
    app.add_handler(CommandHandler("start", protected(cmd_start)))
    app.add_handler(CommandHandler("status", protected(cmd_status)))
    app.add_handler(CommandHandler("tasks", protected(cmd_tasks)))
    app.add_handler(CommandHandler("agents", protected(cmd_agents)))
    app.add_handler(CommandHandler("approve", protected(cmd_approve)))
    app.add_handler(CommandHandler("reject", protected(cmd_reject)))
    app.add_handler(CommandHandler("logs", protected(cmd_logs)))
    app.add_handler(CommandHandler("projects", protected(cmd_projects)))
    app.add_handler(CommandHandler("memory", protected(cmd_memory)))
    app.add_handler(CommandHandler("github", protected(cmd_github)))
    app.add_handler(CommandHandler("settings", protected(cmd_settings)))
    app.add_handler(CommandHandler("help", protected(cmd_help)))

    # Approval inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(handle_approval_callback, pattern=r"^approval:"))

    logger.info("Dimentos AI Studio OS bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
