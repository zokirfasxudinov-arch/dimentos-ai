"""
Dimentos AI Studio OS - Telegram Menu System
Inline keyboard navigation for all sections.
All callback_data use prefix: menu:<section>[:<sub>][:<id>]
"""
from __future__ import annotations

import json
from typing import Union

import httpx
from loguru import logger
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from telegram.ext import ContextTypes

from core.config import settings

API_BASE = f"http://localhost:{settings.api_port}"


# ──────────────────────────────────────────────
# Keyboard builders
# ──────────────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💰 Заработок",         callback_data="menu:earn"),
            InlineKeyboardButton("🟢 Состояние",         callback_data="menu:status"),
        ],
        [
            InlineKeyboardButton("🤖 AI-агенты",         callback_data="menu:agents"),
            InlineKeyboardButton("✅ Подтверждения",     callback_data="menu:approvals"),
        ],
        [
            InlineKeyboardButton("📋 Задачи",            callback_data="menu:tasks"),
            InlineKeyboardButton("📁 Проекты",           callback_data="menu:projects"),
        ],
        [
            InlineKeyboardButton("🧠 Память",            callback_data="menu:memory"),
            InlineKeyboardButton("🔗 GitHub",            callback_data="menu:github"),
        ],
        [
            InlineKeyboardButton("📜 Логи",              callback_data="menu:logs"),
            InlineKeyboardButton("⚙️ Настройки",        callback_data="menu:settings"),
        ],
        [
            InlineKeyboardButton("❓ Помощь",            callback_data="menu:help"),
        ],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:main"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main"),
    ]])


def kb_back_row() -> list:
    return [
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:main"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main"),
    ]


# ──────────────────────────────────────────────
# API helper
# ──────────────────────────────────────────────

async def _get(path: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE}{path}", timeout=8)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.warning(f"API GET {path}: {e}")
    return None


async def _post(path: str, body: dict) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{API_BASE}{path}", json=body, timeout=8)
            if r.status_code == 200:
                return r.json()
    except Exception as e:
        logger.warning(f"API POST {path}: {e}")
    return None


# ──────────────────────────────────────────────
# Send / edit helpers
# ──────────────────────────────────────────────

async def _reply(update: Update, text: str, keyboard: InlineKeyboardMarkup, parse_mode: str = "HTML") -> None:
    """Send or edit a message depending on whether this is a callback or a command."""
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode=parse_mode)
        except Exception:
            await update.callback_query.message.reply_text(text, reply_markup=keyboard, parse_mode=parse_mode)
    elif update.message:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=parse_mode)


# ──────────────────────────────────────────────
# 🏠 Main menu
# ──────────────────────────────────────────────

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🤖 <b>Dimentos AI Studio OS</b>\n\n"
        "Выберите, что нужно сделать:"
    )
    await _reply(update, text, kb_main())


# ──────────────────────────────────────────────
# 🟢 System status
# ──────────────────────────────────────────────

async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    health = await _get("/health")
    ai_status = await _get("/api/ai/status")
    approvals = await _get("/api/approvals?status=pending")
    tasks = await _get("/api/tasks?limit=100")

    if not health:
        text = "❌ <b>API недоступен</b>\n\nПроверь контейнеры Docker."
        await _reply(update, text, kb_back())
        return

    db = health.get("services", {}).get("db", "?")
    redis = health.get("services", {}).get("redis", "?")
    overall = health.get("status", "unknown")

    db_icon = "🟢" if db == "ok" else "🔴"
    redis_icon = "🟢" if redis == "ok" else "🔴"
    overall_icon = "🟢" if overall == "ok" else "🔴"

    providers = ai_status.get("providers", []) if ai_status else []
    ai_line = f"🤖 <b>AI провайдеры:</b> {', '.join(providers) or 'не настроены'}"

    pending_count = approvals.get("total", 0) if approvals else 0
    approval_icon = "⚠️" if pending_count > 0 else "✅"

    active_tasks = 0
    failed_tasks = 0
    if tasks:
        for t in tasks.get("items", []):
            if t.get("status") == "in_progress":
                active_tasks += 1
            elif t.get("status") == "failed":
                failed_tasks += 1

    text = (
        f"{overall_icon} <b>Состояние системы</b>\n\n"
        f"{db_icon} База данных (PostgreSQL): <b>{'работает' if db == 'ok' else 'ошибка'}</b>\n"
        f"{redis_icon} Redis (очередь): <b>{'работает' if redis == 'ok' else 'ошибка'}</b>\n"
        f"🌐 Веб-панель: <b>порт 3000</b>\n"
        f"🔗 API: <b>порт 8001</b>\n\n"
        f"{ai_line}\n\n"
        f"{approval_icon} Ожидают подтверждения: <b>{pending_count}</b>\n"
        f"📋 Задач активных: <b>{active_tasks}</b>\n"
        f"{'❌' if failed_tasks else '✅'} Задач с ошибкой: <b>{failed_tasks}</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:status")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# 📋 Tasks
# ──────────────────────────────────────────────

async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/tasks?limit=20")
    if not data:
        await _reply(update, "❌ Не удалось загрузить задачи.", kb_back())
        return

    items = data.get("items", [])
    if not items:
        await _reply(update, "ℹ️ <b>Задач нет.</b>\n\nАI-агенты ещё не создавали задач.", kb_back())
        return

    STATUS_ICONS = {
        "pending":     "🕐",
        "in_progress": "🔄",
        "done":        "✅",
        "failed":      "❌",
    }

    lines = ["📋 <b>Задачи</b>\n"]
    buttons = []
    for task in items[:15]:
        icon = STATUS_ICONS.get(task.get("status", ""), "❓")
        title = (task.get("title") or "Без названия")[:40]
        agent = task.get("agent", "?")
        lines.append(f"{icon} <b>{title}</b>\n   <i>{agent}</i> · {task.get('status', '?')}")
        tid = task.get("id", "")
        if tid:
            buttons.append([
                InlineKeyboardButton(f"👁 {title[:20]}", callback_data=f"menu:task:{tid[:8]}"),
            ])

    buttons.append(kb_back_row())
    await _reply(update, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def show_task_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: str) -> None:
    data = await _get(f"/api/tasks/{task_id}")
    if not data:
        await _reply(update, f"❌ Задача `{task_id}` не найдена.", kb_back())
        return

    text = (
        f"📋 <b>Задача</b>\n\n"
        f"<b>Название:</b> {data.get('title', '?')}\n"
        f"<b>Агент:</b> {data.get('agent', '?')}\n"
        f"<b>Статус:</b> {data.get('status', '?')}\n"
        f"<b>Приоритет:</b> {data.get('priority', 'medium')}\n"
        f"<b>Описание:</b> {(data.get('description') or '—')[:200]}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Остановить", callback_data=f"task:stop:{task_id}"),
            InlineKeyboardButton("🔁 Повторить",  callback_data=f"task:retry:{task_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Удалить", callback_data=f"task:delete:{task_id}"),
        ],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# 🤖 Agents
# ──────────────────────────────────────────────

async def show_agents(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/agents/status")
    if not data:
        await _reply(update, "❌ Не удалось загрузить статусы агентов.", kb_back())
        return

    agents = data.get("agents", {})
    if not agents:
        await _reply(update, "ℹ️ Агенты не зарегистрированы.", kb_back())
        return

    STATUS_ICONS = {"active": "🟢", "idle": "🟡", "error": "🔴", "stopped": "⭕"}
    lines = ["🤖 <b>AI-агенты</b>\n"]
    buttons = []

    for name, info in agents.items():
        icon = STATUS_ICONS.get(info.get("status", ""), "⭕")
        desc = (info.get("description") or "")[:50]
        last = info.get("last_run", "никогда")
        lines.append(f"{icon} <b>{info.get('name', name)}</b>\n   {desc}\n   Последний запуск: <i>{last}</i>")
        buttons.append([
            InlineKeyboardButton(f"▶️ {name}", callback_data=f"agent:run:{name}"),
            InlineKeyboardButton(f"📜 Логи",   callback_data=f"menu:logs:agent:{name}"),
        ])

    buttons.append(kb_back_row())
    await _reply(update, "\n".join(lines), InlineKeyboardMarkup(buttons))


# ──────────────────────────────────────────────
# ✅ Approvals
# ──────────────────────────────────────────────

async def show_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/approvals?status=pending")
    if not data:
        await _reply(update, "❌ Не удалось загрузить запросы.", kb_back())
        return

    items = data.get("items", [])
    if not items:
        text = (
            "✅ <b>Подтверждения</b>\n\n"
            "Нет запросов, ожидающих решения.\n\n"
            "Когда AI-агент захочет выполнить важное действие, "
            "уведомление придёт сюда автоматически."
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Обновить", callback_data="menu:approvals")],
            kb_back_row(),
        ])
        await _reply(update, text, keyboard)
        return

    text = (
        f"✅ <b>Подтверждения</b>\n\n"
        f"Ожидают решения: <b>{len(items)}</b>\n\n"
        "Выберите запрос для просмотра:"
    )

    RISK_ICONS = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    buttons = []
    for item in items[:8]:
        risk = item.get("risk_level", "MEDIUM")
        icon = RISK_ICONS.get(risk, "⚪")
        agent = item.get("agent", "?")
        action = (item.get("action") or "?")[:25]
        iid = item["id"]
        buttons.append([
            InlineKeyboardButton(
                f"{icon} {agent}: {action}",
                callback_data=f"menu:approval:{iid[:16]}",
            )
        ])

    buttons.append([InlineKeyboardButton("🔄 Обновить", callback_data="menu:approvals")])
    buttons.append(kb_back_row())
    await _reply(update, text, InlineKeyboardMarkup(buttons))


async def show_approval_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, approval_id: str) -> None:
    # Find the full ID from prefix
    data = await _get("/api/approvals?status=pending")
    full_id = approval_id
    if data:
        for item in data.get("items", []):
            if item["id"].startswith(approval_id):
                full_id = item["id"]
                break

    detail = await _get(f"/api/approvals/{full_id}")
    if not detail:
        await _reply(update, "❌ Запрос не найден.", kb_back())
        return

    RISK_ICONS = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
    risk = detail.get("risk_level", "MEDIUM")
    risk_icon = RISK_ICONS.get(risk, "⚪")

    RISK_REASONS = {
        "LOW":    "Безопасное действие, можно выполнить.",
        "MEDIUM": "Действие затрагивает данные или внешние системы.",
        "HIGH":   "⚠️ Критическое действие! Внимательно проверьте перед подтверждением.",
    }

    text = (
        f"⚠️ <b>Запрос на подтверждение</b>\n\n"
        f"<b>Агент:</b> {detail.get('agent', '?')}\n"
        f"<b>Действие:</b> {detail.get('action', '?')}\n"
        f"{risk_icon} <b>Риск:</b> {risk}\n\n"
        f"<b>Что будет сделано:</b>\n{detail.get('description', '?')}\n\n"
        f"<i>{RISK_REASONS.get(risk, '')}</i>\n\n"
        f"<code>ID: {full_id[:8]}...</code>"
    )

    if risk == "HIGH":
        # For HIGH risk, first show pre-confirmation
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚠️ Подтвердить (HIGH риск)", callback_data=f"menu:approval:confirm_high:{full_id[:16]}")],
            [InlineKeyboardButton("❌ Отклонить", callback_data=f"approval:reject:{full_id}")],
            [InlineKeyboardButton("⬅️ К списку",   callback_data="menu:approvals")],
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"approval:approve:{full_id}"),
                InlineKeyboardButton("❌ Отклонить",   callback_data=f"approval:reject:{full_id}"),
            ],
            [
                InlineKeyboardButton("⏳ Отложить",   callback_data=f"approval:defer:{full_id}"),
                InlineKeyboardButton("⬅️ К списку",   callback_data="menu:approvals"),
            ],
        ])

    await _reply(update, text, keyboard)


async def show_approval_high_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, approval_id: str) -> None:
    # Expand short ID
    data = await _get("/api/approvals?status=pending")
    full_id = approval_id
    if data:
        for item in data.get("items", []):
            if item["id"].startswith(approval_id):
                full_id = item["id"]
                break

    detail = await _get(f"/api/approvals/{full_id}")
    action = detail.get("action", "?") if detail else "?"

    text = (
        "🔴 <b>Подтверждение HIGH риска</b>\n\n"
        f"Действие: <b>{action}</b>\n\n"
        "Вы точно хотите выполнить это действие?\n"
        "Оно помечено как <b>HIGH RISK</b> и может иметь серьёзные последствия."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Да, выполнить", callback_data=f"approval:approve:{full_id}")],
        [InlineKeyboardButton("❌ Нет, отменить", callback_data=f"approval:reject:{full_id}")],
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# 📁 Projects
# ──────────────────────────────────────────────

async def show_projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/projects")
    if not data:
        await _reply(update, "❌ Не удалось загрузить проекты.", kb_back())
        return

    items = data.get("items", [])
    if not items:
        text = "ℹ️ <b>Проекты</b>\n\nПроектов ещё нет. Они появятся когда AI-агенты начнут работу."
        await _reply(update, text, kb_back())
        return

    STATUS_ICONS = {"active": "🟢", "paused": "🟡", "completed": "✅", "error": "🔴"}
    lines = ["📁 <b>Проекты</b>\n"]
    buttons = []

    for p in items[:10]:
        icon = STATUS_ICONS.get(p.get("status", ""), "⭕")
        name = p.get("name", "?")
        desc = (p.get("description") or "")[:50]
        lines.append(f"{icon} <b>{name}</b>\n   {desc}")
        pid = p.get("id", "")
        if pid:
            buttons.append([
                InlineKeyboardButton(f"👁 {name[:20]}",    callback_data=f"menu:project:{pid[:8]}"),
                InlineKeyboardButton("📋 Задачи",         callback_data=f"menu:tasks"),
            ])

    buttons.append(kb_back_row())
    await _reply(update, "\n".join(lines), InlineKeyboardMarkup(buttons))


# ──────────────────────────────────────────────
# 🧠 Memory
# ──────────────────────────────────────────────

async def show_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/memory/notes")

    total = data.get("total", 0) if data else 0
    notes = data.get("notes", []) if data else []

    sections: dict[str, int] = {}
    for note in notes:
        section = note.split("/")[0] if "/" in note else "Корень"
        sections[section] = sections.get(section, 0) + 1

    section_lines = "\n".join(f"  • {s}: {c} зап." for s, c in sorted(sections.items())) or "  пусто"

    text = (
        "🧠 <b>Память системы</b>\n\n"
        "Здесь хранятся важные заметки, решения, настройки "
        "и история работы AI-агентов.\n\n"
        f"<b>Всего записей:</b> {total}\n\n"
        f"<b>По разделам:</b>\n{section_lines}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 Найти запись",     callback_data="menu:memory:search"),
            InlineKeyboardButton("📋 Последние записи", callback_data="menu:memory:recent"),
        ],
        [
            InlineKeyboardButton("➕ Добавить запись",  callback_data="menu:memory:add"),
            InlineKeyboardButton("🔄 Обновить",         callback_data="menu:memory"),
        ],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# 🔗 GitHub
# ──────────────────────────────────────────────

async def show_github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/github/status")

    if not data:
        text = (
            "🔗 <b>GitHub</b>\n\n"
            "❌ Не удалось получить статус.\n"
            "Проверь GITHUB_TOKEN в настройках."
        )
        await _reply(update, text, kb_back())
        return

    configured = data.get("configured", False)
    user = data.get("user", "не настроен")
    repo = data.get("repo", "?")

    text = (
        "🔗 <b>GitHub</b>\n\n"
        f"<b>Статус:</b> {'✅ Подключён' if configured else '❌ Не настроен'}\n"
        f"<b>Аккаунт:</b> {user}\n"
        f"<b>Репозиторий:</b> {repo}\n\n"
        f"{'Готов к работе.' if configured else '⚠️ Установи GITHUB_TOKEN в .env'}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Проверить GitHub", callback_data="menu:github")],
        [
            InlineKeyboardButton("⬆️ Отправить (push)", callback_data="github:push"),
            InlineKeyboardButton("⬇️ Получить (pull)",  callback_data="github:pull"),
        ],
        [InlineKeyboardButton("📜 История коммитов",   callback_data="github:history")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# 📜 Logs
# ──────────────────────────────────────────────

async def show_logs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📜 <b>Логи системы</b>\n\n"
        "Выберите, что посмотреть:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Последние ошибки",  callback_data="menu:logs:errors")],
        [InlineKeyboardButton("🤖 Логи бота",         callback_data="menu:logs:bot")],
        [InlineKeyboardButton("🧠 Логи агентов",      callback_data="menu:logs:agents")],
        [InlineKeyboardButton("🌐 Логи API",          callback_data="menu:logs:api")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


async def show_logs_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/logs/agent?limit=20")
    if not data:
        await _reply(update, "❌ Не удалось получить логи агентов.", InlineKeyboardMarkup([kb_back_row()]))
        return

    items = data.get("items", [])
    if not items:
        await _reply(update, "ℹ️ Логов агентов нет.", InlineKeyboardMarkup([kb_back_row()]))
        return

    lines = ["🧠 <b>Логи агентов</b>\n"]
    for log in items[:15]:
        ts = (log.get("timestamp") or "")[:16]
        agent = log.get("agent_name", "?")
        action = (log.get("action") or "")[:40]
        result = (log.get("result") or "")[:30]
        lines.append(f"<code>{ts}</code> [{agent}] {action} → {result}")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:logs:agents")],
        kb_back_row(),
    ])
    await _reply(update, "\n".join(lines), keyboard)


async def show_logs_errors(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail=30", "dimentos_api"],
            capture_output=True, text=True, timeout=10,
        )
        raw = result.stderr or result.stdout or ""
        errors = [l for l in raw.splitlines() if "ERROR" in l or "error" in l.lower()][-20:]
        if not errors:
            text = "✅ <b>Последние ошибки</b>\n\nОшибок не найдено."
        else:
            text = "❌ <b>Последние ошибки</b>\n\n<code>" + "\n".join(errors[-15:])[:3000] + "</code>"
    except Exception as e:
        text = f"❌ Не удалось прочитать логи: {e}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:logs:errors")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


async def show_logs_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail=30", "dimentos_bot"],
            capture_output=True, text=True, timeout=10,
        )
        raw = (result.stdout or "") + (result.stderr or "")
        lines = raw.splitlines()[-25:]
        text = "🤖 <b>Логи бота</b>\n\n<code>" + "\n".join(lines)[:3000] + "</code>"
    except Exception as e:
        text = f"❌ Не удалось прочитать логи бота: {e}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:logs:bot")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


async def show_logs_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "logs", "--tail=30", "dimentos_api"],
            capture_output=True, text=True, timeout=10,
        )
        raw = (result.stdout or "") + (result.stderr or "")
        lines = raw.splitlines()[-25:]
        text = "🌐 <b>Логи API</b>\n\n<code>" + "\n".join(lines)[:3000] + "</code>"
    except Exception as e:
        text = f"❌ Не удалось прочитать логи API: {e}"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:logs:api")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# ⚙️ Settings
# ──────────────────────────────────────────────

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    providers = settings.available_providers
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"<b>Домен:</b> {settings.domain}\n"
        f"<b>API порт:</b> {settings.api_port}\n"
        f"<b>Лог уровень:</b> {settings.log_level}\n"
        f"<b>GitHub:</b> {settings.github_user or 'не настроен'}\n\n"
        f"<b>AI провайдеры ({len(providers)}):</b>\n"
        + "\n".join(f"  • {p}" for p in providers)
        + ("\n\n<i>Токены и пароли скрыты в целях безопасности.</i>" if providers else "\n\n⚠️ Нет активных AI провайдеров.")
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 AI-модели",     callback_data="menu:settings:ai")],
        [InlineKeyboardButton("🔐 Безопасность",  callback_data="menu:settings:security")],
        [InlineKeyboardButton("🔔 Уведомления",   callback_data="menu:settings:notify")],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


async def show_settings_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/ai/status")
    if not data:
        await _reply(update, "❌ AI статус недоступен.", kb_back())
        return

    providers = data.get("providers", [])
    models = data.get("default_models", {})
    priority = data.get("priority_order", [])
    free_models = data.get("openrouter_free_models", [])

    lines = ["🤖 <b>AI-модели</b>\n"]
    for p in priority:
        m = models.get(p, "?")
        lines.append(f"  • <b>{p}</b>: <code>{m}</code>")

    if free_models:
        lines.append("\n<b>Бесплатные модели OpenRouter:</b>")
        for m in free_models[:4]:
            lines.append(f"  • <code>{m}</code>")

    if not providers:
        lines.append("\n⚠️ Ни один провайдер не настроен!\nДобавь ключи в .env файл.")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="menu:settings:ai")],
        [InlineKeyboardButton("⬅️ Настройки", callback_data="menu:settings")],
        kb_back_row(),
    ])
    await _reply(update, "\n".join(lines), keyboard)


# ──────────────────────────────────────────────
# ❓ Help
# ──────────────────────────────────────────────

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Этот бот нужен для управления <b>Dimentos AI Studio OS</b>.\n\n"
        "<b>Что можно делать:</b>\n"
        "🟢 Проверять состояние системы\n"
        "📋 Смотреть задачи AI-агентов\n"
        "🤖 Управлять AI-агентами\n"
        "✅ Подтверждать или отклонять важные действия\n"
        "📁 Смотреть проекты\n"
        "📜 Смотреть ошибки и логи\n"
        "🔗 Проверять статус GitHub\n"
        "🧠 Работать с памятью системы\n\n"
        "<b>Начните с:</b>\n"
        "• <b>Состояние системы</b> — всё ли работает?\n"
        "• <b>Подтверждения</b> — ждёт ли AI вашего решения?\n\n"
        "<b>Главные команды:</b>\n"
        "<code>/task</code> — поставить задачу агенту (зарабатывает для вас)\n"
        "<code>/ai</code> — быстрый вопрос к AI\n"
        "<code>/approve</code> — подтвердить действие агента\n"
        "<code>/status</code> — состояние системы"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🟢 Состояние системы", callback_data="menu:status"),
            InlineKeyboardButton("✅ Подтверждения",      callback_data="menu:approvals"),
        ],
        kb_back_row(),
    ])
    await _reply(update, text, keyboard)


# ──────────────────────────────────────────────
# Main callback dispatcher
# ──────────────────────────────────────────────

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes all menu:* callbacks to the correct handler."""
    query = update.callback_query
    if not query:
        return

    # Security check
    if update.effective_user and update.effective_user.id != settings.telegram_owner_id:
        await query.answer("⛔ Доступ запрещён.")
        return

    await query.answer()

    data = query.data  # e.g. "menu:status", "menu:logs:errors", "task:stop:id123"
    parts = data.split(":", 3)  # max 4 parts
    prefix = parts[0]  # "menu", "task", "agent", "github"

    # Handle non-menu prefixes
    if prefix == "task":
        action = parts[1] if len(parts) > 1 else ""
        tid = parts[2] if len(parts) > 2 else ""
        if action == "stop":
            await _reply(update, f"⏸ Задача <code>{tid}</code> остановлена (не реализовано).", kb_back())
        elif action == "retry":
            await _reply(update, f"🔁 Задача <code>{tid}</code> перезапущена (не реализовано).", kb_back())
        elif action == "delete":
            await _reply(update, f"🗑 Задача <code>{tid}</code> удалена (не реализовано).", kb_back())
        return

    if prefix == "agent":
        action = parts[1] if len(parts) > 1 else ""
        agent_name = parts[2] if len(parts) > 2 else ""
        if action == "run":
            result_data = await _post(f"/api/agents/{agent_name}/run", {"task": "manual_trigger", "params": {}})
            if result_data:
                await _reply(update, f"▶️ Агент <b>{agent_name}</b> запущен.\n\nРезультат: <code>{str(result_data)[:200]}</code>", kb_back())
            else:
                await _reply(update, f"❌ Не удалось запустить агента <b>{agent_name}</b>.", kb_back())
        return

    if prefix == "github":
        action = parts[1] if len(parts) > 1 else ""
        await _handle_github_action(update, context, action)
        return

    # Default: menu: prefix
    section = parts[1] if len(parts) > 1 else "main"

    if section == "main":
        await show_main_menu(update, context)

    elif section == "status":
        await show_status(update, context)

    elif section == "tasks":
        await show_tasks(update, context)

    elif section == "task" and len(parts) >= 3:
        await show_task_detail(update, context, parts[2])

    elif section == "agents":
        await show_agents(update, context)

    elif section == "approvals":
        await show_approvals(update, context)

    elif section == "approval":
        if len(parts) >= 4 and parts[2] == "confirm_high":
            await show_approval_high_confirm(update, context, parts[3])
        elif len(parts) >= 3:
            await show_approval_detail(update, context, parts[2])
        else:
            await show_approvals(update, context)

    elif section == "projects":
        await show_projects(update, context)

    elif section == "memory":
        sub = parts[2] if len(parts) > 2 else None
        if sub == "recent":
            await show_memory_recent(update, context)
        elif sub == "search":
            await query.message.reply_text(
                "🔎 <b>Поиск по памяти</b>\n\nОтправьте запрос командой:\n<code>/memory search &lt;текст&gt;</code>",
                parse_mode="HTML",
            )
        elif sub == "add":
            await query.message.reply_text(
                "➕ <b>Добавить запись</b>\n\nОтправьте запрос командой:\n<code>/memory add &lt;заголовок&gt; &lt;текст&gt;</code>",
                parse_mode="HTML",
            )
        else:
            await show_memory(update, context)

    elif section == "github":
        sub = parts[2] if len(parts) > 2 else None
        if sub == "push":
            await _handle_github_action(update, context, "push")
        elif sub == "pull":
            await _handle_github_action(update, context, "pull")
        elif sub == "history":
            await _handle_github_action(update, context, "history")
        else:
            await show_github(update, context)

    elif section == "logs":
        sub = parts[2] if len(parts) > 2 else None
        if sub == "errors":
            await show_logs_errors(update, context)
        elif sub == "bot":
            await show_logs_bot(update, context)
        elif sub == "agents":
            await show_logs_agent(update, context)
        elif sub == "api":
            await show_logs_api(update, context)
        else:
            await show_logs_menu(update, context)

    elif section == "settings":
        sub = parts[2] if len(parts) > 2 else None
        if sub == "ai":
            await show_settings_ai(update, context)
        elif sub == "security":
            await _reply(update, "🔐 <b>Безопасность</b>\n\nВладелец: <code>настроен</code>\nAccess denied для всех чужих пользователей: <b>включено</b>", kb_back())
        elif sub == "notify":
            await _reply(update, "🔔 <b>Уведомления</b>\n\nТелеграм-уведомления: <b>включены</b>\nApproval flow: <b>включён</b>", kb_back())
        else:
            await show_settings(update, context)

    elif section == "earn":
        sub = parts[2] if len(parts) > 2 else None
        if sub == "opps":
            await show_opportunities(update, context)
        elif sub == "opp" and len(parts) >= 4:
            await show_opportunity_detail(update, context, parts[3])
        elif sub == "analyze" and len(parts) >= 4:
            await _handle_analyze(update, context, parts[3])
        elif sub == "propose" and len(parts) >= 4:
            await _handle_opportunity_propose(update, context, parts[3])
        elif sub == "payments":
            await show_payments(update, context)
        elif sub == "leads":
            await show_leads(update, context)
        elif sub == "lead" and len(parts) >= 4:
            await show_lead_detail(update, context, parts[3])
        elif sub == "search":
            await _handle_lead_search(update, context)
        elif sub == "earnings":
            await show_earnings(update, context)
        else:
            await show_earn(update, context)

    elif section == "help":
        await show_help(update, context)

    else:
        await show_main_menu(update, context)


async def show_memory_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/memory/notes")
    if not data:
        await _reply(update, "❌ Память недоступна.", kb_back())
        return

    notes = data.get("notes", [])[:10]
    if not notes:
        await _reply(update, "ℹ️ Записей нет.", kb_back())
        return

    lines = ["📋 <b>Последние записи памяти</b>\n"]
    for note in notes:
        lines.append(f"  • <code>{note}</code>")

    await _reply(update, "\n".join(lines), InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Память", callback_data="menu:memory")],
        kb_back_row(),
    ]))


async def show_earn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Earnings dashboard."""
    stats = await _get("/api/opportunities/stats")
    payments = await _get("/api/payments")

    if stats:
        by_status = stats.get("by_status", {})
        total_earned = stats.get("total_earned_usd", 0)
        total_pending = stats.get("total_pending_usd", 0)

        status_icons = {
            "NEW_FOUND": "🆕", "ANALYZED": "🔍", "GOOD_FIT": "⭐",
            "PROPOSAL_DRAFTED": "📝", "WAITING_APPROVAL": "⏳",
            "PROPOSAL_SENT": "📤", "CLIENT_REPLIED": "💬",
            "NEGOTIATION": "🤝", "ACCEPTED": "✅", "IN_PROGRESS": "🔨",
            "QA": "🧪", "DELIVERY_READY": "📦", "DELIVERED": "🚀",
            "PAID": "💰", "ARCHIVED": "🗄",
        }

        active_statuses = ["NEW_FOUND", "GOOD_FIT", "PROPOSAL_DRAFTED",
                           "WAITING_APPROVAL", "PROPOSAL_SENT", "NEGOTIATION",
                           "ACCEPTED", "IN_PROGRESS"]
        active_count = sum(by_status.get(s, 0) for s in active_statuses)

        lines = [
            "💰 <b>Earn Dashboard</b>\n",
            f"📊 Всего проектов: <b>{stats.get('total', 0)}</b>",
            f"🔥 Активных: <b>{active_count}</b>",
            f"⭐ Средний скор: <b>{stats.get('avg_score', 0)}/100</b>",
            f"\n💵 Заработано: <b>${total_earned:.2f}</b>",
            f"⏳ Ожидает оплаты: <b>${total_pending:.2f}</b>",
        ]
        if by_status.get("GOOD_FIT"):
            lines.append(f"\n⭐ Хороших проектов: <b>{by_status['GOOD_FIT']}</b> — готовы к отклику")
        if by_status.get("WAITING_APPROVAL"):
            lines.append(f"⏳ Ждут подтверждения: <b>{by_status['WAITING_APPROVAL']}</b>")
        text = "\n".join(lines)
    else:
        text = "💰 <b>Earn Dashboard</b>\n\nСтатистика недоступна."

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Все проекты",   callback_data="menu:earn:opps"),
            InlineKeyboardButton("💵 Оплаты",        callback_data="menu:earn:payments"),
        ],
        [
            InlineKeyboardButton("🔍 Поиск лидов",  callback_data="menu:earn:search"),
            InlineKeyboardButton("📌 Лиды (RSS)",   callback_data="menu:earn:leads"),
        ],
        kb_back_row(),
    ])
    await _reply(update, text, kb)


async def show_leads(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of scored leads."""
    data = await _get("/api/leads?limit=20")
    if not data:
        await _reply(update, "❌ Лиды недоступны.", kb_back())
        return

    leads = data.get("leads", [])
    if not leads:
        await _reply(
            update,
            "📋 <b>Лиды</b>\n\nПока нет лидов. Нажми «Найти заказы» чтобы начать поиск.",
            InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Найти заказы", callback_data="menu:earn:search")],
                kb_back_row(),
            ])
        )
        return

    STATUS_ICONS = {
        "new": "🆕", "scored": "⭐", "proposal_ready": "📝",
        "sent": "📤", "negotiating": "🤝", "won": "🏆", "lost": "❌",
    }

    lines = [f"📋 <b>Лиды ({len(leads)})</b>\n"]
    buttons = []
    for lead in leads[:10]:
        icon = STATUS_ICONS.get(lead["status"], "•")
        score = f" {lead['ai_score']:.0f}/10" if lead.get("ai_score") else ""
        title = lead["title"][:40]
        lines.append(f"{icon}{score} {title}")
        short_id = lead["id"][:8]
        buttons.append([
            InlineKeyboardButton(
                f"{icon} {title[:30]}",
                callback_data=f"menu:earn:lead:{lead['id']}"
            )
        ])

    buttons.append(kb_back_row())
    await _reply(update, "\n".join(lines), InlineKeyboardMarkup(buttons))


async def show_lead_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    data = await _get(f"/api/leads/{lead_id}")
    if not data:
        await _reply(update, "❌ Лид не найден.", kb_back())
        return

    score_str = f"{data['ai_score']:.0f}/10" if data.get("ai_score") else "не оценён"
    proposal_preview = ""
    if data.get("ai_proposal"):
        proposal_preview = f"\n\n📝 <b>Отклик:</b>\n<code>{data['ai_proposal'][:300]}...</code>"

    text = (
        f"💼 <b>{data['title']}</b>\n\n"
        f"📌 Источник: {data['source']}\n"
        f"💰 Бюджет: {data.get('budget') or 'не указан'}\n"
        f"⭐ Скор: {score_str}\n"
        f"📊 Статус: {data['status']}\n"
    )
    if data.get("ai_analysis"):
        text += f"\n💡 <i>{data['ai_analysis']}</i>"
    if data.get("url"):
        text += f"\n\n🔗 <a href=\"{data['url']}\">Открыть заказ</a>"
    text += proposal_preview

    has_proposal = bool(data.get("ai_proposal"))
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✏️ Сгенерировать отклик" if not has_proposal else "🔄 Обновить отклик",
                callback_data=f"menu:earn:propose:{lead_id}"
            ),
        ],
        [InlineKeyboardButton("⬅️ Все лиды", callback_data="menu:earn:leads")],
        kb_back_row(),
    ])
    await _reply(update, text, kb)


async def _handle_propose(
    update: Update, context: ContextTypes.DEFAULT_TYPE, lead_id: str
) -> None:
    """Generate proposal for a lead."""
    await _reply(update, "⏳ Генерирую отклик через AI...", kb_back())
    data = await _post(f"/api/leads/{lead_id}/propose", {})
    if data and data.get("proposal"):
        proposal = data["proposal"][:800]
        text = f"📝 <b>Готовый отклик:</b>\n\n{proposal}"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ К лиду", callback_data=f"menu:earn:lead:{lead_id}")],
            kb_back_row(),
        ])
        await _reply(update, text, kb)
    else:
        await _reply(update, "❌ Не удалось сгенерировать отклик.", kb_back())


async def _handle_lead_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Trigger background lead search."""
    await _reply(update, "🔍 Запускаю поиск заказов...\n\nПроверяю fl.ru, freelance.ru, habr...", None)
    data = await _post("/api/leads/search", {})
    msg = "✅ Поиск запущен в фоне. Новые лиды появятся через 1-2 минуты." if data else "❌ Ошибка запуска."
    await _reply(update, msg, InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Смотреть лиды", callback_data="menu:earn:leads")],
        kb_back_row(),
    ]))


async def show_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show earning records."""
    data = await _get("/api/earnings")
    if not data:
        await _reply(update, "❌ Данные недоступны.", kb_back())
        return

    records = data.get("earnings", [])
    total = data.get("total_usd", 0)

    if not records:
        text = "💵 <b>Доходы</b>\n\nЗаписей о доходах пока нет.\n\nКогда выиграешь заказ — зафиксируй его через API:\n<code>POST /api/earnings</code>"
    else:
        lines = [f"💵 <b>Доходы (итого: ${total:.2f})</b>\n"]
        for r in records[:10]:
            lines.append(f"  • {r['client']} — ${r['amount_usd']:.2f} ({r['service'][:30]})")
        text = "\n".join(lines)

    await _reply(update, text, kb_back())


async def show_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """CRM opportunity list."""
    data = await _get("/api/opportunities?limit=20")
    if not data:
        await _reply(update, "❌ CRM недоступен.", kb_back())
        return

    opps = data.get("opportunities", [])
    if not opps:
        text = (
            "📋 <b>Проекты (CRM)</b>\n\n"
            "Проектов пока нет.\n\n"
            "Добавь проект командой:\n"
            "<code>/submit https://upwork.com/...</code>"
        )
        await _reply(update, text, InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Найти заказы", callback_data="menu:earn:search")],
            kb_back_row(),
        ]))
        return

    STATUS_ICONS = {
        "NEW_FOUND": "🆕", "ANALYZED": "🔍", "GOOD_FIT": "⭐",
        "PROPOSAL_DRAFTED": "📝", "WAITING_APPROVAL": "⏳",
        "PROPOSAL_SENT": "📤", "CLIENT_REPLIED": "💬", "NEGOTIATION": "🤝",
        "ACCEPTED": "✅", "IN_PROGRESS": "🔨", "QA": "🧪",
        "DELIVERED": "🚀", "PAID": "💰", "ARCHIVED": "🗄",
    }

    buttons = []
    for opp in opps[:12]:
        icon = STATUS_ICONS.get(opp["status"], "•")
        score_str = f" {opp['score']:.0f}" if opp.get("score") else ""
        label = f"{icon}{score_str} {opp['title'][:35]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"menu:earn:opp:{opp['id']}")])

    buttons.append(kb_back_row())
    text = f"📋 <b>Проекты ({len(opps)})</b>\n\nСкор | Статус | Название"
    await _reply(update, text, InlineKeyboardMarkup(buttons))


async def show_opportunity_detail(
    update: Update, context: ContextTypes.DEFAULT_TYPE, opp_id: str
) -> None:
    data = await _get(f"/api/opportunities/{opp_id}")
    if not data:
        await _reply(update, "❌ Проект не найден.", kb_back())
        return

    score = data.get("score")
    score_str = f"{score:.0f}/100" if score else "не оценён"
    score_bar = ""
    if score:
        filled = int(score / 10)
        score_bar = "█" * filled + "░" * (10 - filled)

    price_str = ""
    if data.get("pricing_normal"):
        price_str = (
            f"\n💵 Цены: от ${data.get('pricing_min', '?'):.0f} | "
            f"${data['pricing_normal']:.0f} | "
            f"${data.get('pricing_premium', '?'):.0f} premium"
        )

    proposal_preview = ""
    if data.get("ai_proposal"):
        proposal_preview = f"\n\n📝 <b>Отклик:</b>\n<i>{data['ai_proposal'][:300]}...</i>"

    text = (
        f"💼 <b>{data['title']}</b>\n\n"
        f"📌 Источник: {data['source']}\n"
        f"📊 Статус: <b>{data['status']}</b>\n"
        f"⭐ Скор: <b>{score_str}</b> {score_bar}\n"
        f"💰 Бюджет: {data.get('budget_raw') or 'не указан'}"
        f"{price_str}"
    )
    if data.get("ai_analysis"):
        text += f"\n\n💡 <i>{data['ai_analysis']}</i>"
    if data.get("source_url"):
        text += f"\n\n🔗 <a href=\"{data['source_url']}\">Открыть проект</a>"
    text += proposal_preview

    has_proposal = bool(data.get("ai_proposal"))
    has_analysis = bool(data.get("ai_analysis"))

    rows = []
    if not has_analysis:
        rows.append([InlineKeyboardButton("🔍 Анализировать", callback_data=f"menu:earn:analyze:{opp_id}")])
    if has_analysis and not has_proposal:
        rows.append([InlineKeyboardButton("📝 Написать отклик", callback_data=f"menu:earn:propose:{opp_id}")])
    if has_proposal:
        rows.append([InlineKeyboardButton("🔄 Обновить отклик", callback_data=f"menu:earn:propose:{opp_id}")])
    rows.append([InlineKeyboardButton("⬅️ Все проекты", callback_data="menu:earn:opps")])
    rows.append(kb_back_row())
    await _reply(update, text, InlineKeyboardMarkup(rows))


async def _handle_analyze(
    update: Update, context: ContextTypes.DEFAULT_TYPE, opp_id: str
) -> None:
    await _reply(update, "⏳ AI анализирует проект...", None)
    data = await _post(f"/api/opportunities/{opp_id}/analyze", {})
    if data and not data.get("result", "").startswith("Ошибка"):
        result_text = data.get("result", "")
        d = data.get("data", {})
        score = d.get("score", 0)
        text = (
            f"📊 <b>Анализ завершён</b>\n\n"
            f"⭐ Скор: <b>{score}/100</b>\n"
            f"{'✅ Рекомендован' if d.get('recommended') else '⚠️ Не рекомендован'}\n"
            f"💡 {result_text}\n\n"
            f"Пакет: <b>{d.get('recommended_package', 'custom')}</b>"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Написать отклик", callback_data=f"menu:earn:propose:{opp_id}")],
            [InlineKeyboardButton("⬅️ К проекту", callback_data=f"menu:earn:opp:{opp_id}")],
            kb_back_row(),
        ])
    else:
        text = f"❌ Ошибка анализа: {data.get('result', '') if data else 'API недоступен'}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:earn:opp:{opp_id}")]])
    await _reply(update, text, kb)


async def _handle_opportunity_propose(
    update: Update, context: ContextTypes.DEFAULT_TYPE, opp_id: str
) -> None:
    await _reply(update, "⏳ AI пишет персональный отклик...", None)
    data = await _post(f"/api/opportunities/{opp_id}/propose", {})
    if data and data.get("proposal"):
        proposal = data["proposal"]
        price = data.get("data", {}).get("price")
        text = (
            f"📝 <b>Отклик готов</b>"
            + (f" (${price:.0f})" if price else "")
            + f"\n\n{proposal[:1200]}"
            + ("\n\n<i>...обрезан до 1200 символов</i>" if len(proposal) > 1200 else "")
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Отправить на подтверждение", callback_data=f"menu:earn:opp:{opp_id}")],
            [InlineKeyboardButton("⬅️ К проекту", callback_data=f"menu:earn:opp:{opp_id}")],
            kb_back_row(),
        ])
    else:
        text = f"❌ Ошибка: {data.get('result', '') if data else 'API недоступен'}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"menu:earn:opp:{opp_id}")]])
    await _reply(update, text, kb)


async def show_payments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = await _get("/api/payments")
    if not data:
        await _reply(update, "❌ Данные недоступны.", kb_back())
        return

    payments = data.get("payments", [])
    gross = data.get("total_gross", 0)
    net = data.get("total_net", 0)

    if not payments:
        text = "💵 <b>Оплаты</b>\n\nПлатежей пока нет.\n\nКогда получишь оплату — зафикси через API:\n<code>POST /api/payments</code>"
    else:
        lines = [f"💵 <b>Оплаты</b>  Gross: ${gross:.2f} | Net: ${net:.2f}\n"]
        for p in payments[:10]:
            status_icon = {"received": "✅", "pending": "⏳", "withdrawn": "💸"}.get(p["status"], "•")
            lines.append(
                f"{status_icon} ${p['amount_gross']:.0f}"
                + (f" → ${p['amount_net']:.0f}" if p.get("amount_net") else "")
                + f" | {p.get('platform', '?')}"
            )
        text = "\n".join(lines)

    await _reply(update, text, kb_back())


async def _handle_github_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    ACTION_LABELS = {"push": "отправить изменения", "pull": "получить изменения", "history": "историю"}
    label = ACTION_LABELS.get(action, action)
    # These actions require approval
    data = await _post("/api/approvals/create", {
        "agent": "github_agent",
        "action": f"github_{action}",
        "description": f"Запрос на GitHub: {label}",
        "risk_level": "MEDIUM",
    })
    if data:
        await _reply(update, f"⚠️ Запрос на подтверждение создан.\n\nДействие: <b>{label}</b>\nID: <code>{data.get('id', '?')[:8]}...</code>\n\nПроверьте раздел ✅ Подтверждения.", kb_back())
    else:
        await _reply(update, "❌ Не удалось создать запрос.", kb_back())
