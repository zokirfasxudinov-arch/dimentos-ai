"""
Security Agent - Scans for leaked secrets, checks risks, audits configs.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from agents.base import BaseAgent, ActionResult, RiskLevel
from core.security import scan_for_secrets


class SecurityAgent(BaseAgent):
    """
    Security Agent scans code, configs, and vault for security issues.
    All scan operations are LOW risk (read-only).
    Fixing/patching is MEDIUM risk.
    """

    name = "security"
    default_risk_level = RiskLevel.LOW

    # Patterns for detecting common secret formats
    DANGEROUS_PATTERNS = [
        (re.compile(r"(?i)password\s*[=:]\s*['\"]?.{8,}"), "Hardcoded password"),
        (re.compile(r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{16,}"), "API key"),
        (re.compile(r"sk-[A-Za-z0-9]{20,}"), "OpenAI key pattern"),
        (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub PAT"),
        (re.compile(r"[A-Za-z0-9]{32,}:[A-Za-z0-9\-_]{10,}"), "Bot token pattern"),
        (re.compile(r"(?i)secret\s*[=:]\s*['\"]?.{8,}"), "Hardcoded secret"),
        (re.compile(r"(?i)TELEGRAM_BOT_TOKEN\s*=\s*[0-9]{8,}:"), "Telegram token"),
    ]

    SAFE_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".env.example", ".sh", ".sql", ".md"}
    SKIP_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build"}

    async def execute(self, task: str, params: Optional[dict] = None) -> ActionResult:
        params = params or {}
        task_lower = task.lower()

        if "scan" in task_lower or "check" in task_lower:
            path = params.get("path", "/opt/dimentos-ai")
            return await self._scan_directory(Path(path))
        elif "file" in task_lower:
            path = params.get("path", "")
            if not path:
                return ActionResult(success=False, error="path parameter required")
            return await self._scan_file(Path(path))
        elif "audit" in task_lower:
            return await self._audit_environment()
        else:
            return await self._scan_directory(Path("/opt/dimentos-ai"))

    async def _scan_directory(self, directory: Path) -> ActionResult:
        """Scan all files in a directory for secrets."""
        if not directory.exists():
            return ActionResult(success=False, error=f"Directory not found: {directory}")

        all_findings = []
        scanned_files = 0

        for file_path in directory.rglob("*"):
            # Skip directories and non-relevant dirs
            if file_path.is_dir():
                continue
            if any(skip in file_path.parts for skip in self.SKIP_DIRS):
                continue
            # Skip .env (expected to have secrets)
            if file_path.name == ".env":
                continue
            if file_path.suffix not in self.SAFE_EXTENSIONS and file_path.suffix != "":
                continue

            try:
                findings = await self._scan_file(file_path)
                if findings.data and findings.data.get("findings"):
                    all_findings.extend([
                        {**f, "file": str(file_path)}
                        for f in findings.data["findings"]
                    ])
                scanned_files += 1
            except Exception:
                pass

        severity = "clean" if not all_findings else ("critical" if len(all_findings) > 5 else "warning")
        self.logger.info(f"Security scan: {scanned_files} files, {len(all_findings)} findings")

        return ActionResult(
            success=True,
            data={
                "scanned_files": scanned_files,
                "findings": all_findings,
                "total_findings": len(all_findings),
                "severity": severity,
            },
        )

    async def _scan_file(self, file_path: Path) -> ActionResult:
        """Scan a single file for secrets."""
        if not file_path.exists():
            return ActionResult(success=False, error=f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return ActionResult(success=False, error=str(e))

        findings = []
        for i, line in enumerate(content.splitlines(), 1):
            for pattern, label in self.DANGEROUS_PATTERNS:
                if pattern.search(line):
                    findings.append({
                        "line": i,
                        "type": label,
                        "preview": line[:80].strip(),
                    })
                    break  # one finding per line

        return ActionResult(
            success=True,
            data={
                "file": str(file_path),
                "findings": findings,
                "clean": len(findings) == 0,
            },
        )

    async def _audit_environment(self) -> ActionResult:
        """Check environment configuration for security issues."""
        from core.config import settings

        issues = []

        if not settings.api_secret_key:
            issues.append("API_SECRET_KEY is not set - API is unprotected")
        if not settings.telegram_owner_id:
            issues.append("TELEGRAM_OWNER_ID is not set - bot accepts commands from anyone")

        # Check .env file
        env_path = Path("/opt/dimentos-ai/.env")
        if env_path.exists():
            # Verify .gitignore protects it
            gitignore_path = Path("/opt/dimentos-ai/.gitignore")
            if gitignore_path.exists():
                gitignore = gitignore_path.read_text()
                if ".env" not in gitignore:
                    issues.append(".env is NOT in .gitignore - risk of committing secrets!")

        severity = "ok" if not issues else ("critical" if len(issues) > 2 else "warning")

        return ActionResult(
            success=True,
            data={
                "severity": severity,
                "issues": issues,
                "total_issues": len(issues),
                "recommendation": "Fix all CRITICAL issues before deployment",
            },
        )
