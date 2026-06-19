from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class XConfig(BaseModel):
    bearer_token_env: str = "X_BEARER_TOKEN"
    username: str = "thsottiaux"
    query: str = (
        'from:thsottiaux (Codex OR tokens OR "rate limits" OR "usage limits" '
        'OR "paid plans" OR reset OR "you know what\'s coming") -is:retweet'
    )
    max_results: int = 20

    @property
    def bearer_token(self) -> str | None:
        return os.getenv(self.bearer_token_env)


class GitHubConfig(BaseModel):
    token_env: str = "GITHUB_TOKEN"
    repo: str = "openai/codex"
    query: str = '"rate limit" OR "usage limit" OR "reset credits"'
    max_results: int = 20

    @property
    def token(self) -> str | None:
        return os.getenv(self.token_env)


class ClassifierConfig(BaseModel):
    mode: Literal["rules", "hybrid", "llm"] = "rules"
    candidate_score: float = 0.55
    notify_score: float = 0.80


class LLMConfig(BaseModel):
    provider: str = "openai-compatible"
    model: str = "gpt-4.1-mini"
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str | None = None
    use_response_format: Literal["auto", "always", "never"] | None = None
    temperature: float = 0
    timeout_seconds: float = 45
    max_retries: int = 2
    extra_headers: dict[str, str] = Field(default_factory=dict)
    extra_body: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def apply_provider_preset(self) -> "LLMConfig":
        preset = PROVIDER_PRESETS.get(self.provider, PROVIDER_PRESETS["openai-compatible"])
        if self.base_url is None:
            self.base_url = preset["base_url"]
        if self.use_response_format is None:
            self.use_response_format = preset["use_response_format"]
        return self

    @property
    def api_key(self) -> str | None:
        return os.getenv(self.api_key_env)


class NotifyConfig(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["console"])
    min_level: Literal["low", "medium", "high"] = "medium"
    timezone: str = "Asia/Shanghai"
    jsonl_path: Path = Path("events.jsonl")
    telegram_bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    telegram_chat_id_env: str = "TELEGRAM_CHAT_ID"
    discord_webhook_url_env: str = "DISCORD_WEBHOOK_URL"
    email_smtp_host_env: str = "EMAIL_SMTP_HOST"
    email_smtp_port_env: str = "EMAIL_SMTP_PORT"
    email_username_env: str = "EMAIL_USERNAME"
    email_password_env: str = "EMAIL_PASSWORD"
    email_from_env: str = "EMAIL_FROM"
    email_to_env: str = "EMAIL_TO"
    email_use_tls_env: str = "EMAIL_USE_TLS"
    email_use_ssl_env: str = "EMAIL_USE_SSL"


class StorageConfig(BaseModel):
    sqlite_path: Path = Path("watcher.sqlite3")


class AppConfig(BaseModel):
    x: XConfig = Field(default_factory=XConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    classifier: ClassifierConfig = Field(default_factory=ClassifierConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    notify: NotifyConfig = Field(default_factory=NotifyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return AppConfig.model_validate(data)


PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "use_response_format": "always",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "use_response_format": "auto",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "use_response_format": "auto",
    },
    "litellm": {
        "base_url": "http://localhost:4000/v1",
        "use_response_format": "never",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "use_response_format": "never",
    },
    "openai-compatible": {
        "base_url": "https://api.openai.com/v1",
        "use_response_format": "auto",
    },
}
