"""
Proposal Agent - Writes proposals, TZs, client documents using AI.
NEVER sends to external parties without explicit HIGH approval.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.ai_providers import ai


class ProposalAgent(BaseAgent):
    name = "proposal"
    default_risk_level = RiskLevel.LOW

    SYSTEM_PROMPT = """Ты — профессиональный бизнес-аналитик и технический писатель Dimentos AI Studio.
Пишешь коммерческие предложения, технические задания и документацию на русском языке.
Стиль: деловой, чёткий, убедительный. Структурируй через заголовки Markdown."""

    def assess_risk(self, task: str, params: Optional[dict] = None) -> str:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["send", "email", "publish", "submit", "upload"]):
            return RiskLevel.HIGH
        if any(kw in task_lower for kw in ["finalize", "approve", "sign"]):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["draft", "write", "create", "generate", "написать", "создать"]):
            return await self._draft_with_ai(
                title=params.get("title", task),
                client=params.get("client", ""),
                requirements=params.get("requirements", task),
                proposal_type=params.get("type", "general"),
            )
        elif "list" in task_lower:
            return await self._list_proposals()
        elif "send" in task_lower:
            return ActionResult(success=False, error="Отправка требует подтверждения HIGH через Telegram.")
        else:
            # Default: treat the whole task as a document request
            return await self._draft_with_ai(title=task, requirements=task)

    async def _draft_with_ai(
        self,
        title: str,
        client: str = "",
        requirements: str = "",
        proposal_type: str = "general",
    ) -> ActionResult:
        timestamp = datetime.now().strftime("%Y-%m-%d")

        TYPE_PROMPTS = {
            "general":  "Напиши коммерческое предложение",
            "tz":       "Напиши техническое задание (ТЗ)",
            "contract": "Напиши шаблон договора",
            "report":   "Напиши отчёт",
        }
        doc_type = TYPE_PROMPTS.get(proposal_type, "Напиши документ")

        prompt = (
            f"{doc_type} на тему: \"{title}\"\n\n"
            f"Клиент: {client or 'не указан'}\n"
            f"Требования / контекст:\n{requirements or title}\n\n"
            "Включи: описание проекта, scope работ, технологии, сроки, стоимость (примерную), условия.\n"
            "Используй Markdown разметку. Документ должен быть готов к отправке клиенту."
        )

        try:
            response = await ai.chat(
                prompt=prompt,
                system=self.SYSTEM_PROMPT,
                max_tokens=3000,
            )
            content = response.text
            self.logger.info(f"AI drafted proposal via {response.provider}: {len(content)} chars")
        except Exception as e:
            self.logger.warning(f"AI draft failed, using template: {e}")
            content = self._template(title, client, requirements, timestamp)

        # Save to vault
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)[:50].strip().replace(" ", "_")
        vault_path = Path("/app/obsidian-vault/12_TZ")
        vault_path.mkdir(parents=True, exist_ok=True)
        filename = f"{timestamp}_{safe_title}.md"
        full_content = f"# {title}\n**Дата:** {timestamp} | **Клиент:** {client or 'TBD'} | **Статус:** ЧЕРНОВИК\n\n---\n\n{content}"
        (vault_path / filename).write_text(full_content, encoding="utf-8")

        return ActionResult(success=True, data={
            "title": title,
            "path": f"12_TZ/{filename}",
            "status": "draft",
            "content": full_content,
            "provider": getattr(response if 'response' in dir() else None, 'provider', 'template'),
            "chars": len(content),
        })

    def _template(self, title: str, client: str, requirements: str, timestamp: str) -> str:
        return f"""## Описание проекта
{requirements or 'Требования уточняются.'}

## Scope работ
- Анализ требований
- Проектирование архитектуры
- Разработка
- Тестирование и QA
- Деплой и документация

## Технологии
- Python / FastAPI
- PostgreSQL + Redis
- Docker / Docker Compose
- Telegram Bot API

## Сроки
| Этап | Срок |
|------|------|
| Анализ | 1 нед. |
| Разработка | 3–4 нед. |
| Тестирование | 1 нед. |
| Деплой | 3 дня |

## Стоимость
По результатам оценки трудозатрат.

## Условия
- Предоплата 50%, остаток при сдаче
- Гарантия 30 дней

> **ЧЕРНОВИК — требует подтверждения перед отправкой**"""

    async def _list_proposals(self) -> ActionResult:
        vault_path = Path("/app/obsidian-vault/12_TZ")
        if not vault_path.exists():
            return ActionResult(success=True, data={"proposals": [], "total": 0})
        proposals = [
            {"filename": f.name, "path": f"12_TZ/{f.name}", "size": f.stat().st_size}
            for f in sorted(vault_path.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)
        ]
        return ActionResult(success=True, data={"proposals": proposals, "total": len(proposals)})
