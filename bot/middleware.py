"""
Bot middleware - owner-only access control.
"""
from __future__ import annotations

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from core.config import settings


async def owner_only_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Returns True if the user is the owner, False otherwise.
    Sends an 'access denied' message to unauthorized users.
    """
    if not settings.telegram_owner_id:
        # Owner not configured - deny everyone for safety
        if update.effective_message:
            await update.effective_message.reply_text(
                "Bot is not configured yet. Set TELEGRAM_OWNER_ID in .env"
            )
        logger.warning("Command received but TELEGRAM_OWNER_ID is not configured")
        return False

    user = update.effective_user
    if user is None:
        return False

    if user.id != settings.telegram_owner_id:
        logger.warning(f"Unauthorized access attempt from user {user.id} (@{user.username})")
        if update.effective_message:
            await update.effective_message.reply_text("Access denied.")
        return False

    return True
