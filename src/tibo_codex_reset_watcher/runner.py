from __future__ import annotations

import os
from dataclasses import dataclass
from rich.console import Console

from tibo_codex_reset_watcher.classifier.llm import LLMClassifier
from tibo_codex_reset_watcher.classifier.rules import RuleClassifier
from tibo_codex_reset_watcher.config import AppConfig
from tibo_codex_reset_watcher.models import EventType, RawItem, ResetEvent, Severity
from tibo_codex_reset_watcher.notify import ConsoleNotifier, DiscordNotifier, EmailNotifier, JsonlNotifier, TelegramNotifier
from tibo_codex_reset_watcher.sources import GitHubSource, XApiSource
from tibo_codex_reset_watcher.storage import SQLiteStore


SEVERITY_RANK = {
    Severity.NONE: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
}

console = Console(stderr=True)


@dataclass
class RunResult:
    fetched: int
    new_items: int
    events: list[ResetEvent]
    notified: int
    stored: int


class WatcherRunner:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.rules = RuleClassifier(
            notify_score=config.classifier.notify_score,
            candidate_score=config.classifier.candidate_score,
        )
        self.llm = LLMClassifier(config.llm)

    async def fetch(self, source: str) -> list[RawItem]:
        if source == "x":
            return await XApiSource(self.config.x).fetch()
        if source == "github":
            return await GitHubSource(self.config.github).fetch_commits()
        raise ValueError(f"Unknown source: {source}")

    async def classify(self, item: RawItem) -> ResetEvent:
        rule_event = self.rules.classify(item)
        mode = self.config.classifier.mode
        if mode == "rules":
            return rule_event
        if mode == "llm":
            return await self.llm.classify(item, rule_event)
        if mode == "hybrid" and rule_event.confidence >= self.config.classifier.candidate_score:
            try:
                return await self.llm.classify(item, rule_event)
            except Exception as exc:
                console.print(f"[yellow]LLM classify failed, falling back to rules[/yellow] error={exc}")
                return rule_event
        return rule_event

    async def run_once(self, source: str, dry_run: bool = False) -> RunResult:
        raw_items = await self.fetch(source)
        return await self.process_items(raw_items, dry_run=dry_run)

    async def process_items(self, raw_items: list[RawItem], dry_run: bool = False) -> RunResult:
        store = SQLiteStore(self.config.storage.sqlite_path)
        try:
            events: list[ResetEvent] = []
            notified = 0
            new_items = 0
            stored = 0
            for item in raw_items:
                is_new = dry_run or store.save_raw_item(item)
                if not dry_run and is_new:
                    new_items += 1
                if not is_new:
                    continue
                event = await self.classify(item)
                if event.event_type != EventType.UNRELATED:
                    if not dry_run and store.save_event(event):
                        stored += 1
                    events.append(event)
                    if dry_run:
                        continue
                    if self.should_notify(event) and not store.event_already_notified(event):
                        if await self.notify(event):
                            store.mark_notified(event)
                            notified += 1
            return RunResult(
                fetched=len(raw_items),
                new_items=new_items,
                events=events,
                notified=notified,
                stored=stored,
            )
        finally:
            store.close()

    def should_notify(self, event: ResetEvent) -> bool:
        min_level = Severity(self.config.notify.min_level)
        return SEVERITY_RANK[event.severity] >= SEVERITY_RANK[min_level]

    async def notify(self, event: ResetEvent) -> bool:
        delivered = False
        for channel in self.config.notify.channels:
            try:
                if channel == "console":
                    ConsoleNotifier(self.config.notify.timezone).notify(event)
                elif channel == "jsonl":
                    JsonlNotifier(self.config.notify.jsonl_path).notify(event)
                elif channel == "telegram":
                    token = os.getenv(self.config.notify.telegram_bot_token_env)
                    chat_id = os.getenv(self.config.notify.telegram_chat_id_env)
                    if not token or not chat_id:
                        raise RuntimeError("Telegram notification requires bot token and chat id env vars.")
                    await TelegramNotifier(token, chat_id, self.config.notify.timezone).notify(event)
                elif channel == "discord":
                    webhook_url = os.getenv(self.config.notify.discord_webhook_url_env)
                    if not webhook_url:
                        raise RuntimeError("Discord notification requires webhook URL env var.")
                    await DiscordNotifier(webhook_url, self.config.notify.timezone).notify(event)
                elif channel == "email":
                    EmailNotifier(
                        smtp_host=require_env(self.config.notify.email_smtp_host_env),
                        smtp_port=int(require_env(self.config.notify.email_smtp_port_env)),
                        username=require_env(self.config.notify.email_username_env),
                        password=require_env(self.config.notify.email_password_env),
                        from_addr=os.getenv(self.config.notify.email_from_env)
                        or require_env(self.config.notify.email_username_env),
                        to_addr=require_env(self.config.notify.email_to_env),
                        use_tls=parse_bool(os.getenv(self.config.notify.email_use_tls_env, "true")),
                        use_ssl=parse_bool(os.getenv(self.config.notify.email_use_ssl_env, "false")),
                        timezone=self.config.notify.timezone,
                    ).notify(event)
                else:
                    raise ValueError(f"Unknown notify channel: {channel}")
            except Exception as exc:
                console.print(f"[red]Notification channel failed[/red] channel={channel} error={exc}")
                continue
            delivered = True
        return delivered


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
