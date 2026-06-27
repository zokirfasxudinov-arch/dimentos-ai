"""
Telegram bot - Command handlers.
All commands require owner authentication (handled in middleware before calling these).
"""
from __future__ import annotations

from typing import Optional

import httpx
from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from core.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


async def _api_get(path: str) -> Optional[dict]:
    """Helper: GET from API."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}{path}", timeout=10)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.warning(f"API call failed {path}: {e}")
    return None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    await update.message.reply_text(
        "*Dimentos AI Studio OS*\n\n"
        "Система управления AI-агентами запущена.\n\n"
        "Используй /help для просмотра команд.\n"
        "Используй /status для проверки состояния системы.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    help_text = (
        "*Dimentos AI Studio OS - Команды*\n\n"
        "/status - Состояние системы\n"
        "/tasks - Список задач\n"
        "/agents - Статус агентов\n"
        "/approve - Подтвердить ожидающий запрос\n"
        "/reject - Отклонить ожидающий запрос\n"
        "/logs - Последние логи агентов\n"
        "/projects - Список проектов\n"
        "/memory - Просмотр vault памяти\n"
        "/github - Статус GitHub\n"
        "/settings - Настройки бота\n"
        "/help - Эта справка\n\n"
        "_Все действия агентов с риском MEDIUM/HIGH требуют подтверждения._"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status - show system health."""
    data = await _api_get("/health")
    if not data:
        await update.message.reply_text("API недоступен. Проверь контейнеры.")
        return

    db_status = data["services"]["db"]
    redis_status = data["services"]["redis"]
    overall = data["status"]

    status_icon = "green" if overall == "ok" else "red"

    providers_data = await _api_get("/api/finance/usage")
    total_cost = providers_data.get("total_cost_usd", 0.0) if providers_data else 0.0

    msg = (
        f"*Статус системы*\n\n"
        f"Общий: *{overall.upper()}*\n"
        f"БД (PostgreSQL): {db_status}\n"
        f"Redis: {redis_status}\n"
        f"Версия: {data.get('version', '1.0.0')}\n\n"
        f"AI провайдеров активных: {len(settings.available_providers)}\n"
        f"Потрачено (всего): ${total_cost:.4f}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /tasks - list recent tasks."""
    data = await _api_get("/api/tasks?limit=10")
    if not data:
        await update.message.reply_text("Не удалось получить задачи.")
        return

    items = data.get("items", [])
    if not items:
        await update.message.reply_text("Задач нет.")
        return

    lines = ["*Последние задачи:*\n"]
    for task in items[:10]:
        status_icon = {"pending": "", "in_progress": "", "done": "", "failed": ""}.get(task["status"], "")
        lines.append(
            f"{status_icon} *{task['title'][:40]}*\n"
            f"   Агент: {task.get('agent', 'не назначен')} | Статус: {task['status']} | "
            f"Приоритет: {task.get('priority', 'medium')}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /agents - show agent statuses."""
    data = await _api_get("/api/agents/status")
    if not data:
        await update.message.reply_text("Не удалось получить статусы агентов.")
        return

    agents = data.get("agents", {})
    lines = ["*Агенты системы:*\n"]
    for name, info in agents.items():
        lines.append(f"*{info['name']}* - {info['status']}\n   {info['description']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /approve - show pending approvals or approve by ID."""
    args = context.args

    if args:
        # /approve <id>
        approval_id = args[0]
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(
                    f"{API_BASE}/api/approvals/{approval_id}/approve",
                    json={"decided_by": "telegram_owner", "reason": "Approved via /approve command"},
                    timeout=10,
                )
                if r.status_code == 200:
                    await update.message.reply_text(f"Запрос `{approval_id[:8]}...` подтверждён.", parse_mode="Markdown")
                else:
                    await update.message.reply_text(f"Ошибка: {r.text}")
        except Exception as e:
            await update.message.reply_text(f"Ошибка: {e}")
        return

    # No args - list pending approvals
    data = await _api_get("/api/approvals?status=pending")
    if not data:
        await update.message.reply_text("Не удалось получить список запросов.")
        return

    items = data.get("items", [])
    if not items:
        await update.message.reply_text("Нет ожидающих запросов на подтверждение.")
        return

    from bot.handlers.approvals import _make_approval_keyboard

    for item in items[:5]:  # Show max 5
        text = (
            f"*Ожидает подтверждения*\n\n"
            f"*Агент:* {item['agent']}\n"
            f"*Действие:* {item['action']}\n"
            f"*Риск:* {item['risk_level']}\n"
            f"*Описание:* {item['description']}\n"
            f"ID: `{item['id'][:8]}...`"
        )
        keyboard = _make_approval_keyboard(item["id"])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /reject <id> - reject an approval request."""
    args = context.args
    if not args:
        await update.message.reply_text("Использование: /reject <id>")
        return

    approval_id = args[0]
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/approvals/{approval_id}/reject",
                json={"decided_by": "telegram_owner", "reason": "Rejected via /reject command"},
                timeout=10,
            )
            if r.status_code == 200:
                await update.message.reply_text(f"Запрос `{approval_id[:8]}...` отклонён.", parse_mode="Markdown")
            else:
                await update.message.reply_text(f"Ошибка: {r.text}")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


async def cmd_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /logs - show recent agent logs."""
    data = await _api_get("/api/logs/agent?limit=10")
    if not data:
        await update.message.reply_text("Не удалось получить логи.")
        return

    items = data.get("items", [])
    if not items:
        await update.message.reply_text("Логов нет.")
        return

    lines = ["*Последние логи агентов:*\n"]
    for log in items[:10]:
        ts = log.get("timestamp", "")[:16] if log.get("timestamp") else "?"
        lines.append(f"`{ts}` [{log['agent_name']}] {log['action']} - {log.get('result', '')[:40]}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /projects - list all projects."""
    data = await _api_get("/api/projects")
    if not data:
        await update.message.reply_text("Не удалось получить проекты.")
        return

    items = data.get("items", [])
    if not items:
        await update.message.reply_text("Проектов нет.")
        return

    lines = ["*Проекты:*\n"]
    for p in items:
        lines.append(f"*{p['name']}* - {p['status']}\n   {p.get('description', '')[:60]}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /memory - show vault stats."""
    data = await _api_get("/api/memory/notes")
    if not data:
        await update.message.reply_text("Vault недоступен.")
        return

    total = data.get("total", 0)
    notes = data.get("notes", [])

    # Group by section
    sections: dict[str, int] = {}
    for note in notes:
        section = note.split("/")[0] if "/" in note else "root"
        sections[section] = sections.get(section, 0) + 1

    lines = [f"*Obsidian Vault*\nВсего заметок: {total}\n"]
    for section, count in sorted(sections.items()):
        lines.append(f"  {section}: {count} заметок")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /github - GitHub status."""
    data = await _api_get("/api/github/status")
    if not data:
        await update.message.reply_text("GitHub API недоступен.")
        return

    configured = data.get("configured", False)
    user = data.get("user", "не настроен")

    msg = (
        f"*GitHub Integration*\n\n"
        f"Статус: {'настроен' if configured else 'не настроен'}\n"
        f"Пользователь: `{user}`\n\n"
        f"{'Токен установлен.' if configured else 'Установи GITHUB_TOKEN в .env'}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings - show current non-sensitive settings."""
    msg = (
        f"*Настройки Dimentos AI Studio OS*\n\n"
        f"Домен: `{settings.domain}`\n"
        f"API порт: `{settings.api_port}`\n"
        f"Log level: `{settings.log_level}`\n"
        f"AI провайдеры: `{', '.join(settings.available_providers) or 'не настроены'}`\n"
        f"GitHub user: `{settings.github_user or 'не настроен'}`\n\n"
        f"_Токены и пароли не отображаются из соображений безопасности._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
