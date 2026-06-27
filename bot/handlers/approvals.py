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

    await query.answer()  # Acknowledge button press (removes loading indicator)

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
            f"✅ <b>Подтверждено</b>\n\nЗапрос <code>{approval_id[:8]}...</code> принят.\nАгент продолжит выполнение.",
            parse_mode="HTML",
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
            f"❌ <b>Отклонено</b>\n\nЗапрос <code>{approval_id[:8]}...</code> отклонён.\nДействие НЕ будет выполнено.",
            parse_mode="HTML",
        )
        logger.info(f"Approval {approval_id} REJECTED via Telegram")
    except Exception as e:
        await query.edit_message_text(f"Failed to reject: {e}")
        logger.error(f"Failed to reject {approval_id}: {e}")


async def _handle_defer(query, approval_id: str) -> None:
    """Defer an approval (mark as deferred but keep it pending)."""
    await query.edit_message_text(
        f"⏳ <b>Отложено</b>\n\nЗапрос <code>{approval_id[:8]}...</code> отложен.\n\n"
        "Используй /approve или /reject позже, или нажми ✅ Подтверждения в меню.",
        parse_mode="HTML",
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

        RISK_ICONS = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
        risk = data.get("risk_level", "MEDIUM")
        details = (
            f"👁 <b>Подробная информация</b>\n\n"
            f"<b>ID:</b> <code>{data['id'][:8]}...</code>\n"
            f"<b>Агент:</b> {data['agent']}\n"
            f"<b>Действие:</b> {data['action']}\n"
            f"{RISK_ICONS.get(risk, '⚪')} <b>Риск:</b> {risk}\n"
            f"<b>Статус:</b> {data['status']}\n"
            f"<b>Описание:</b> {data['description']}\n"
            f"<b>Запрошено:</b> {data['requested_at'][:19]}"
            f"{payload_str}"
        )

        keyboard = _make_approval_keyboard(approval_id, risk)
        await query.edit_message_text(details, parse_mode="HTML", reply_markup=keyboard)

    except Exception as e:
        await query.edit_message_text(f"Could not fetch details: {e}")


def _make_approval_keyboard(approval_id: str, risk_level: str = "MEDIUM") -> InlineKeyboardMarkup:
    """Build the approval inline keyboard. HIGH risk uses pre-confirmation flow."""
    short_id = approval_id[:16]
    if risk_level == "HIGH":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Подтвердить (HIGH)", callback_data=f"menu:approval:confirm_high:{short_id}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"approval:reject:{approval_id}")],
            [
                InlineKeyboardButton("⏳ Отложить",  callback_data=f"approval:defer:{approval_id}"),
                InlineKeyboardButton("👁 Подробнее", callback_data=f"approval:details:{approval_id}"),
            ],
        ])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"approval:approve:{approval_id}"),
            InlineKeyboardButton("❌ Отклонить",   callback_data=f"approval:reject:{approval_id}"),
        ],
        [
            InlineKeyboardButton("⏳ Отложить",   callback_data=f"approval:defer:{approval_id}"),
            InlineKeyboardButton("👁 Подробнее",  callback_data=f"approval:details:{approval_id}"),
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

    RISK_ICONS = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    risk_icon = RISK_ICONS.get(risk_level, "⚪")

    text = (
        f"⚠️ <b>Запрос на подтверждение</b>\n\n"
        f"<b>Агент:</b> {agent}\n"
        f"<b>Действие:</b> {action}\n"
        f"{risk_icon} <b>Риск:</b> {risk_level}\n"
        f"<b>Описание:</b> {description}\n\n"
        f"<code>ID: {approval_id[:8]}...</code>"
    )

    keyboard = _make_approval_keyboard(approval_id, risk_level)

    try:
        await bot.send_message(
            chat_id=settings.telegram_owner_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        logger.info(f"Approval request sent to owner: {approval_id}")
    except Exception as e:
        logger.error(f"Failed to send approval notification: {e}")
