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
    """Handle /start — show main menu."""
    from bot.handlers.menu import show_main_menu
    await show_main_menu(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help — show help section."""
    from bot.handlers.menu import show_help
    await show_help(update, context)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status."""
    from bot.handlers.menu import show_status
    await show_status(update, context)


async def _cmd_status_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /status - kept for reference."""
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
    """Handle /tasks."""
    from bot.handlers.menu import show_tasks
    await show_tasks(update, context)


async def _cmd_tasks_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /tasks."""
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
    """Handle /agents."""
    from bot.handlers.menu import show_agents
    await show_agents(update, context)


async def _cmd_agents_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /agents."""
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
    """Handle /logs."""
    from bot.handlers.menu import show_logs_menu
    await show_logs_menu(update, context)


async def _cmd_logs_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /logs."""
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
    """Handle /projects."""
    from bot.handlers.menu import show_projects
    await show_projects(update, context)


async def _cmd_projects_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /projects."""
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
    """Handle /memory."""
    from bot.handlers.menu import show_memory
    await show_memory(update, context)


async def _cmd_memory_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /memory."""
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
    """Handle /github."""
    from bot.handlers.menu import show_github
    await show_github(update, context)


async def _cmd_github_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /github."""
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
    """Handle /settings."""
    from bot.handlers.menu import show_settings
    await show_settings(update, context)


async def _cmd_settings_old(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy /settings."""
    providers = settings.available_providers
    msg = (
        f"*Настройки Dimentos AI Studio OS*\n\n"
        f"Домен: `{settings.domain}`\n"
        f"API порт: `{settings.api_port}`\n"
        f"Log level: `{settings.log_level}`\n"
        f"AI провайдеры ({len(providers)}): `{', '.join(providers) or 'не настроены'}`\n"
        f"GitHub user: `{settings.github_user or 'не настроен'}`\n\n"
        f"_Токены и пароли не отображаются из соображений безопасности._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ai <prompt> — quick AI chat directly from Telegram."""
    if not context.args:
        providers = settings.available_providers
        data = await _api_get("/api/ai/status")
        provider_lines = ""
        if data:
            for p in data.get("providers", []):
                m = data.get("default_models", {}).get(p, "")
                provider_lines += f"\n  • {p}: `{m}`"
        await update.message.reply_text(
            f"*AI Провайдеры*\n\n"
            f"Активных: {len(providers)}{provider_lines}\n\n"
            f"Использование: `/ai <вопрос>`\n"
            f"Принудительно: `/ai [anthropic|gemini|openrouter|groq] <вопрос>`",
            parse_mode="Markdown",
        )
        return

    args = context.args
    # Check if first arg is provider name
    known_providers = ["anthropic", "gemini", "openrouter", "groq", "openai"]
    provider = None
    if args[0].lower() in known_providers:
        provider = args[0].lower()
        prompt = " ".join(args[1:])
    else:
        prompt = " ".join(args)

    if not prompt:
        await update.message.reply_text("Укажи вопрос после команды.")
        return

    thinking_msg = await update.message.reply_text("Думаю...")

    try:
        body: dict = {"prompt": prompt, "max_tokens": 1500}
        if provider:
            body["provider"] = provider

        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/ai/chat",
                json=body,
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()

        text = data["text"]
        prov_info = f"_{data['provider']} / {data['model']}_"

        # Telegram message limit is 4096 chars
        reply = f"{text[:3800]}\n\n{prov_info}" if len(text) > 3800 else f"{text}\n\n{prov_info}"
        await thinking_msg.edit_text(reply, parse_mode="Markdown")

    except Exception as e:
        await thinking_msg.edit_text(f"Ошибка AI: {e}")


# ──────────────────────────────────────────────────────────────────
# /task — главная команда для постановки задач агентам
# ──────────────────────────────────────────────────────────────────

AGENT_KEYWORDS = {
    "research":  ["найди", "исследуй", "поищи", "проанализируй", "изучи", "проверь рынок", "кто", "что такое", "как работает"],
    "proposal":  ["напиши", "составь", "создай", "предложение", "ТЗ", "техническое задание", "договор", "коммерческое"],
    "security":  ["безопасность", "уязвимость", "секрет", "скан", "audit"],
    "memory":    ["запомни", "сохрани", "запиши в память", "добавь в vault"],
    "github":    ["github", "репозиторий", "коммит", "пуш", "репо"],
    "finance":   ["расходы", "бюджет", "стоимость", "сколько потратили"],
    "ceo":       ["спланируй", "разбей", "план", "стратегия", "делегируй"],
}


def _pick_agent_for_task(task: str) -> str:
    task_lower = task.lower()
    for agent, keywords in AGENT_KEYWORDS.items():
        if any(kw in task_lower for kw in keywords):
            return agent
    return "research"  # default


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /task <описание> — поставить задачу агенту.

    Агент выбирается автоматически по ключевым словам.
    Принудительно: /task research найди клиентов
    """
    if not context.args:
        await update.message.reply_text(
            "📋 *Постановка задачи агентам*\n\n"
            "Использование: `/task <задача>`\n\n"
            "Примеры:\n"
            "• `/task найди 5 потенциальных клиентов для AI-студии`\n"
            "• `/task напиши коммерческое предложение для веб-агентства`\n"
            "• `/task проанализируй рынок AI-автоматизации в Узбекистане`\n"
            "• `/task составь ТЗ для Telegram-бота с оплатой`\n\n"
            "Агент выбирается автоматически. "
            "Чтобы указать явно: `/task research <задача>`",
            parse_mode="Markdown",
        )
        return

    args = list(context.args)
    # Check if first word is explicit agent name
    explicit_agents = list(AGENT_KEYWORDS.keys())
    if args[0].lower() in explicit_agents:
        agent_name = args[0].lower()
        task_text = " ".join(args[1:])
    else:
        task_text = " ".join(args)
        agent_name = _pick_agent_for_task(task_text)

    if not task_text:
        await update.message.reply_text("Укажи задачу после команды.")
        return

    AGENT_ICONS = {
        "research": "🔍", "proposal": "📝", "ceo": "🧠",
        "memory": "🧩", "github": "🔗", "finance": "💰", "security": "🔐",
    }
    icon = AGENT_ICONS.get(agent_name, "🤖")

    thinking = await update.message.reply_text(
        f"{icon} *{agent_name.upper()} агент* выполняет задачу...\n\n"
        f"_{task_text[:100]}_",
        parse_mode="Markdown",
    )

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{API_BASE}/api/agents/{agent_name}/run",
                json={"task": task_text, "params": {}, "async_run": False},
                timeout=65,
            )
            r.raise_for_status()
            data = r.json()

        if data.get("success"):
            result_data = data.get("data", {})
            # Format the result nicely
            if isinstance(result_data, dict):
                if "result" in result_data:
                    # Research/AI result
                    text = result_data["result"]
                    provider = result_data.get("provider", "")
                    reply = (
                        f"{icon} *Результат ({agent_name})*\n\n"
                        f"{text[:3500]}"
                        f"\n\n_{provider}/{result_data.get('model', '')}_" if provider else ""
                    )
                elif "content" in result_data:
                    # Proposal result
                    content = result_data["content"]
                    path = result_data.get("path", "")
                    reply = (
                        f"📝 *Документ создан*\n\n"
                        f"{content[:3000]}\n\n"
                        f"_Сохранено: {path}_"
                    )
                elif "plan" in result_data or "steps" in result_data:
                    # CEO plan
                    import json
                    reply = (
                        f"🧠 *План выполнения*\n\n"
                        f"```\n{json.dumps(result_data, ensure_ascii=False, indent=2)[:2000]}\n```"
                    )
                else:
                    import json
                    reply = (
                        f"{icon} *Готово!*\n\n"
                        f"```\n{json.dumps(result_data, ensure_ascii=False, indent=2)[:2500]}\n```"
                    )
            else:
                reply = f"{icon} *Готово!*\n\n{str(result_data)[:3000]}"

            # Trim to Telegram limit
            if len(reply) > 4000:
                reply = reply[:3900] + "\n\n_...результат обрезан_"

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Меню", callback_data="menu:main"),
                InlineKeyboardButton("📋 Задачи", callback_data="menu:tasks"),
            ]])
            await thinking.edit_text(reply, parse_mode="Markdown", reply_markup=keyboard)

        else:
            err = data.get("error") or "Неизвестная ошибка"
            await thinking.edit_text(
                f"❌ *Ошибка агента {agent_name}*\n\n{err[:500]}",
                parse_mode="Markdown",
            )

    except asyncio.TimeoutError:
        await thinking.edit_text(
            f"⏱ *Таймаут*\n\nЗадача выполняется дольше 60 секунд. "
            f"Проверь статус в /tasks",
            parse_mode="Markdown",
        )
    except Exception as e:
        await thinking.edit_text(f"❌ Ошибка: {e}")


import asyncio
