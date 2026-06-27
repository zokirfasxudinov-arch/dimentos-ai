"""
Telegram bot - Approval inline keyboard callback handlers.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles inline keyboard button presses for approval flow.
    Callback data format: "approval:<action>:<approval_id>"
    Actions: approve, reject, defer, details
    """
    query = update.callback_query
    if not query:
        return

    # Security: only owner can interact with buttons
    if update.effective_user and update.effective_user.id != settings.telegram_owner_id:
        await query.answer("Access denied.")
        return

    await query.answer()  # Acknowledge the button press

    parts = query.data.split(":", 2)
    if len(parts) < 3:
        await query.edit_message_text("Invalid callback data.")
        return

    _, action, approval_id = parts

    if action == "approve":
        await _handle_approve(query, approval_id)
    elif action == "reject":
        await _handle_reject(query, approval_id)
    elif action == "defer":
        await _handle_defer(query, approval_id)
    elif action == "details":
        await _handle_details(query, approval_id)
    else:
        await query.edit_message_text(f"Unknown action: {action}")


async def _handle_approve(query, approval_id: str) -> None:
    """Approve an action."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/approvals/{approval_id}/approve",
                json={"decided_by": "telegram_owner", "reason": "Approved via Telegram"},
                timeout=10,
            )
            r.raise_for_status()

        await query.edit_message_text(
            f"Approved request `{approval_id[:8]}...`\n\nAgent will proceed with the action.",
            parse_mode="Markdown",
        )
        logger.info(f"Approval {approval_id} APPROVED via Telegram")
    except Exception as e:
        await query.edit_message_text(f"Failed to approve: {e}")
        logger.error(f"Failed to approve {approval_id}: {e}")


async def _handle_reject(query, approval_id: str) -> None:
    """Reject an action."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/approvals/{approval_id}/reject",
                json={"decided_by": "telegram_owner", "reason": "Rejected via Telegram"},
                timeout=10,
            )
            r.raise_for_status()

        await query.edit_message_text(
            f"Rejected request `{approval_id[:8]}...`\n\nAction will NOT be executed.",
            parse_mode="Markdown",
        )
        logger.info(f"Approval {approval_id} REJECTED via Telegram")
    except Exception as e:
        await query.edit_message_text(f"Failed to reject: {e}")
        logger.error(f"Failed to reject {approval_id}: {e}")


async def _handle_defer(query, approval_id: str) -> None:
    """Defer an approval (mark as deferred but keep it pending)."""
    await query.edit_message_text(
        f"Request `{approval_id[:8]}...` deferred.\n\n"
        "Use /approve or /reject later to make a decision.",
        parse_mode="Markdown",
    )
    logger.info(f"Approval {approval_id} DEFERRED by owner")


async def _handle_details(query, approval_id: str) -> None:
    """Show full details of an approval request."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{API_BASE}/api/approvals/{approval_id}",
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()

        payload_str = ""
        if data.get("payload_json"):
            import json
            payload_str = f"\n\n*Payload:*\n```json\n{json.dumps(data['payload_json'], indent=2)[:500]}\n```"

        details = (
            f"*Approval Request Details*\n\n"
            f"*ID:* `{data['id'][:8]}...`\n"
            f"*Agent:* {data['agent']}\n"
            f"*Action:* {data['action']}\n"
            f"*Risk:* {data['risk_level']}\n"
            f"*Status:* {data['status']}\n"
            f"*Description:* {data['description']}\n"
            f"*Requested:* {data['requested_at']}"
            f"{payload_str}"
        )

        keyboard = _make_approval_keyboard(approval_id)
        await query.edit_message_text(details, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as e:
        await query.edit_message_text(f"Could not fetch details: {e}")


def _make_approval_keyboard(approval_id: str) -> InlineKeyboardMarkup:
    """Build the standard approval inline keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Подтвердить", callback_data=f"approval:approve:{approval_id}"),
            InlineKeyboardButton("Отказать", callback_data=f"approval:reject:{approval_id}"),
        ],
        [
            InlineKeyboardButton("Отложить", callback_data=f"approval:defer:{approval_id}"),
            InlineKeyboardButton("Подробнее", callback_data=f"approval:details:{approval_id}"),
        ],
    ])


async def send_approval_request(
    bot,
    approval_id: str,
    agent: str,
    action: str,
    description: str,
    risk_level: str,
) -> None:
    """
    Send an approval request notification to the Telegram owner.
    Called by agents when they need approval.
    """
    if not settings.telegram_owner_id:
        logger.warning("Cannot send approval request: TELEGRAM_OWNER_ID not set")
        return

    risk_emoji = {"LOW": "green_circle", "MEDIUM": "yellow_circle", "HIGH": "red_circle"}.get(risk_level, "white_circle")

    text = (
        f"*Запрос на подтверждение*\n\n"
        f"*Агент:* {agent}\n"
        f"*Действие:* {action}\n"
        f"*Риск:* {risk_level}\n"
        f"*Описание:* {description}\n\n"
        f"ID: `{approval_id[:8]}...`"
    )

    keyboard = _make_approval_keyboard(approval_id)

    try:
        await bot.send_message(
            chat_id=settings.telegram_owner_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        logger.info(f"Approval request sent to owner: {approval_id}")
    except Exception as e:
        logger.error(f"Failed to send approval notification: {e}")
