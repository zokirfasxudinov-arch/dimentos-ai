# Dimentos AI Studio OS

**Боевая платформа автоматизации AI-студии.**

AI максимально автоматизирует работу, но все важные действия выполняются только после подтверждения владельца через Telegram-бота.

## Принцип

```
AI готовит → Владелец подтверждает → AI выполняет
```

## Быстрый старт

```bash
# 1. Настройка
bash scripts/setup.sh

# 2. Заполни .env своими данными

# 3. Запуск
docker compose up -d

# 4. Проверка
curl http://localhost:8000/health

# 5. Web панель
open http://localhost:3000
```

## Архитектура

```
/opt/dimentos-ai/
├── api/          # FastAPI backend
├── bot/          # Telegram Bot (@DimentosControlBot)
├── agents/       # AI Agents (CEO, Memory, GitHub, ...)
├── core/         # Shared: config, DB, models, security
├── web/          # Web panel (HTML + Nginx)
├── memory/       # Obsidian vault manager
├── obsidian-vault/ # Markdown knowledge base
├── tests/        # pytest
├── scripts/      # setup.sh, backup.sh, check_secrets.sh
└── docker/       # Dockerfiles
```

## Стек

| Компонент | Технология |
|---|---|
| Backend | Python FastAPI (async) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Bot | python-telegram-bot 21.x |
| Web | HTML + Tailwind + Nginx |
| Memory | Obsidian Markdown |
| Deploy | Docker Compose |

## Агенты

| Агент | Риск | Описание |
|---|---|---|
| CEO Agent | HIGH | Координатор |
| Memory Agent | LOW | Obsidian vault |
| Research Agent | LOW | Поиск и анализ |
| Developer Agent | MEDIUM | Код |
| GitHub Agent | MEDIUM | Репозитории, коммиты |
| Proposal Agent | HIGH | КП клиентам |
| Finance Agent | MEDIUM | Бюджет, отчёты |
| Security Agent | HIGH | Проверка секретов |
| Freelance Scout | MEDIUM | Поиск проектов |

## Уровни риска

- **LOW** — выполняется автоматически
- **MEDIUM** — требует Telegram подтверждения
- **HIGH** — всегда требует подтверждения

## Telegram бот

Команды: `/start /status /tasks /agents /approve /reject /logs /projects /memory /github /settings /help`

Кнопки: ✅ Подтвердить · ❌ Отказать · ✏ Изменить · ⏳ Отложить · 📄 Подробнее

## API Endpoints

```
GET  /health
GET  /api/agents/status
GET  /api/approvals
POST /api/approvals/create
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/reject
GET  /api/tasks
GET  /api/projects
GET  /api/logs/agents
```

## Безопасность

- Секреты только в `.env` (gitignored)
- Pre-commit hook проверяет каждый коммит
- Push в GitHub только после Telegram подтверждения
- Только `TELEGRAM_OWNER_ID` управляет ботом

## Домен

- `dimentosai.uz` — основной
- `app.dimentosai.uz` — web панель
- `api.dimentosai.uz` — API
- `bot.dimentosai.uz` — bot webhook

---

**GitHub:** zokirfasxudinov-arch | **Domain:** dimentosai.uz
