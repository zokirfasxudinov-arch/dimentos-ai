"""
Dimentos AI Studio OS - Configuration
All settings are loaded from environment variables / .env file.
No secrets are hardcoded here.
"""
from __future__ import annotations

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram
    telegram_bot_token: str = Field(default="", description="Telegram bot token")
    telegram_owner_id: Optional[int] = Field(default=None, description="Telegram owner user ID")

    # Database
    postgres_user: str = Field(default="dimentos")
    postgres_password: str = Field(default="")
    postgres_db: str = Field(default="dimentos_ai")
    database_url: str = Field(default="postgresql+asyncpg://dimentos:password@postgres:5432/dimentos_ai")

    # Redis
    redis_url: str = Field(default="redis://redis:6379/0")

    # API
    api_secret_key: str = Field(default="")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # GitHub
    github_user: str = Field(default="")
    github_email: str = Field(default="")
    github_token: str = Field(default="")

    # AI Providers (all optional)
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    gemini_api_key: str = Field(default="")
    mistral_api_key: str = Field(default="")
    openrouter_api_key: str = Field(default="")
    deepseek_api_key: str = Field(default="")
    perplexity_api_key: str = Field(default="")

    # Domain
    domain: str = Field(default="dimentosai.uz")
    app_url: str = Field(default="https://app.dimentosai.uz")
    api_url: str = Field(default="https://api.dimentosai.uz")

    # Logging
    log_level: str = Field(default="INFO")

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def available_providers(self) -> list[str]:
        providers = []
        if self.has_openai:
            providers.append("openai")
        if self.has_anthropic:
            providers.append("anthropic")
        if self.gemini_api_key:
            providers.append("gemini")
        if self.mistral_api_key:
            providers.append("mistral")
        if self.openrouter_api_key:
            providers.append("openrouter")
        if self.deepseek_api_key:
            providers.append("deepseek")
        if self.perplexity_api_key:
            providers.append("perplexity")
        return providers


# Singleton
settings = Settings()
