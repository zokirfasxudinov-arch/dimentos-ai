"""
Security Agent - Scans for secrets, audits configs, analyzes risks with AI.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.ai_providers import ai
from core.security import scan_for_secrets


class SecurityAgent(BaseAgent):
    name = "security"
    default_risk_level = RiskLevel.LOW

    DANGEROUS_PATTERNS = [
        (re.compile(r"(?i)password\s*[=:]\s*['\"]?.{8,}"), "Hardcoded password"),
        (re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{16,}"), "API key"),
        (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI key"),
        (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub PAT"),
        (re.compile(r"(?i)secret\s*[=:]\s*['\"]?.{8,}"), "Hardcoded secret"),
        (re.compile(r"(?i)TELEGRAM_BOT_TOKEN\s*=\s*[0-9]{8,}:"), "Telegram token"),
    ]

    SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build"}
    SAFE_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".sh", ".sql", ".md"}

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "audit" in task_lower or "environment" in task_lower:
            return await self._audit_environment()
        elif "analyze" in task_lower or "ai" in task_lower:
            result = await self._scan_directory(Path(params.get("path", "/opt/dimentos-ai")))
            if result.success and result.data:
                return await self._ai_analyze(result.data)
            return result
        else:
            return await self._scan_directory(Path(params.get("path", "/opt/dimentos-ai")))

    async def _scan_directory(self, directory: Path) -> ActionResult:
        if not directory.exists():
            return ActionResult(success=False, error=f"Directory not found: {directory}")

        all_findings = []
        scanned = 0
        for file_path in directory.rglob("*"):
            if file_path.is_dir():
                continue
            if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                continue
            if file_path.name == ".env":
                continue
            if file_path.suffix not in self.SAFE_EXTENSIONS:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern, label in self.DANGEROUS_PATTERNS:
                        if pattern.search(line):
                            all_findings.append({
                                "file": str(file_path.relative_to(directory)),
                                "line": i,
                                "type": label,
                                "preview": line[:80].strip(),
                            })
                            break
                scanned += 1
            except Exception:
                pass

        severity = "clean" if not all_findings else ("critical" if len(all_findings) > 3 else "warning")
        return ActionResult(success=True, data={
            "scanned_files": scanned,
            "findings": all_findings,
            "total_findings": len(all_findings),
            "severity": severity,
        })

    async def _ai_analyze(self, scan_data: dict) -> ActionResult:
        findings = scan_data.get("findings", [])
        prompt = (
            f"Анализ безопасности кодовой базы.\n"
            f"Просканировано файлов: {scan_data.get('scanned_files', 0)}\n"
            f"Найдено проблем: {len(findings)}\n\n"
            f"Проблемы:\n" + "\n".join(f"- {f['type']} в {f['file']}:{f['line']}" for f in findings[:10])
            + "\n\nДай краткий анализ рисков и конкретные рекомендации по исправлению."
        )
        try:
            response = await ai.chat(prompt, system="Ты senior security engineer. Отвечай по-русски, кратко и конкретно.", max_tokens=1000)
            scan_data["ai_analysis"] = response.text
            scan_data["ai_provider"] = response.provider
        except Exception as e:
            scan_data["ai_analysis"] = f"AI анализ недоступен: {e}"
        return ActionResult(success=True, data=scan_data)

    async def _audit_environment(self) -> ActionResult:
        from core.config import settings
        issues = []
        if not settings.api_secret_key:
            issues.append({"severity": "HIGH", "issue": "API_SECRET_KEY не установлен — API не защищён"})
        if not settings.telegram_owner_id:
            issues.append({"severity": "HIGH", "issue": "TELEGRAM_OWNER_ID не установлен — бот принимает команды от всех"})
        if not settings.github_token:
            issues.append({"severity": "MEDIUM", "issue": "GITHUB_TOKEN не установлен — GitHub интеграция недоступна"})

        env_path = Path("/opt/dimentos-ai/.env")
        gitignore_path = Path("/opt/dimentos-ai/.gitignore")
        if env_path.exists() and gitignore_path.exists():
            if ".env" not in gitignore_path.read_text():
                issues.append({"severity": "CRITICAL", "issue": ".env НЕ в .gitignore — риск утечки секретов!"})

        severity = "ok" if not issues else ("critical" if any(i["severity"] == "CRITICAL" for i in issues) else "warning")
        return ActionResult(success=True, data={
            "severity": severity,
            "issues": issues,
            "total_issues": len(issues),
        })
