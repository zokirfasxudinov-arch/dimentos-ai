# Changelog

## 2026-06-27 — v0.1.0 — Phase 1 Foundation

### Добавлено
- Структура `/opt/dimentos-ai/` со всеми директориями
- Docker Compose: postgres, redis, api, bot, web
- FastAPI backend с роутерами: health, approvals, agents, tasks, projects, memory, github, finance, logs
- Telegram Bot (@DimentosControlBot) с approval flow
- Inline keyboard: ✅ Подтвердить / ❌ Отказать / ✏ Изменить / ⏳ Отложить / 📄 Подробнее
- Pydantic Settings конфиг (секреты только в .env)
- SQLAlchemy async модели: ApprovalRequest, AgentLog, AuditLog, AIUsageLog, Project, Task
- Агенты (skeleton): CEO, Memory, Research, Developer, QA, Docs, GitHub, Portfolio, LinkedIn, Freelance Scout, Proposal, Finance, Security
- Obsidian Vault структура (15 папок)
- .gitignore (токены, ключи, .env)
- AI Provider Manager в core/config.py

### Принципы
- AI готовит → Владелец подтверждает → AI выполняет
- Секреты только в .env
- Все важные действия логируются

#changelog #v0.1.0
