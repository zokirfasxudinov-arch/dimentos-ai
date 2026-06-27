"""
Dimentos AI Studio OS - Security Utilities
API key validation, secret scanning helpers.
"""
from __future__ import annotations

import re
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> str:
    """FastAPI dependency: validates Bearer token against API_SECRET_KEY."""
    if not settings.api_secret_key:
        # Secret key not configured - allow in dev mode
        return "dev"
    if credentials is None or credentials.credentials != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return credentials.credentials


# Patterns that indicate a potential secret leak
SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[=:]\s*['\"]?[A-Za-z0-9\-_\.]{16,}"),
    re.compile(r"[A-Za-z0-9]{32,}:[A-Za-z0-9\-_]{10,}"),  # bot tokens etc.
    re.compile(r"sk-[A-Za-z0-9]{32,}"),                    # OpenAI keys
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                    # GitHub PAT
]


def scan_for_secrets(content: str) -> list[str]:
    """
    Scan text content for potential leaked secrets.
    Returns list of warnings.
    """
    warnings: list[str] = []
    for i, line in enumerate(content.splitlines(), 1):
        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                warnings.append(f"Potential secret on line {i}: {line[:60]}...")
                break
    return warnings
