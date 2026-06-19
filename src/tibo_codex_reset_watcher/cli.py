from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from tibo_codex_reset_watcher.classifier.rules import RuleClassifier
from tibo_codex_reset_watcher.config import AppConfig, load_config
from tibo_codex_reset_watcher.models import EventType, RawItem, ResetEvent, Severity, SourceKind
from tibo_codex_reset_watcher.runner import WatcherRunner
from tibo_codex_reset_watcher.storage.sqlite import event_to_json_line

app = typer.Typer(help="Watch Tibo-style Codex reset hints and announcements.")
console = Console()


ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", help="Path to config YAML file."),
]


@app.command()
def classify_text(
    text: Annotated[str, typer.Argument(help="Post text to classify.")],
    created_at: Annotated[
        str | None,
        typer.Option(help="ISO timestamp for the source post. Defaults to now UTC."),
    ] = None,
    author: Annotated[str, typer.Option(help="Author handle.")] = "thsottiaux",
    mode: Annotated[str, typer.Option(help="Classifier mode: rules, hybrid, or llm.")] = "rules",
    config: ConfigOption = None,
    json_output: Annotated[bool, typer.Option("--json", help="Print JSON only.")] = False,
) -> None:
    """Classify one text sample with rules, hybrid, or LLM mode."""
    created = parse_dt(created_at) if created_at else datetime.now(timezone.utc)
    item = RawItem(
        source=SourceKind.FIXTURE,
        source_id="manual",
        author=author,
        text=text,
        created_at=created,
        url=None,
    )
    if mode == "rules":
        event = RuleClassifier().classify(item)
    elif mode in {"hybrid", "llm"}:
        cfg = load_config(config)
        cfg.classifier.mode = mode
        event = asyncio.run(WatcherRunner(cfg).classify(item))
    else:
        raise typer.BadParameter("mode must be one of: rules, hybrid, llm")
    if json_output:
        console.print(event_to_json_line(event))
    else:
        from tibo_codex_reset_watcher.notify.console import ConsoleNotifier

        ConsoleNotifier().notify(event)


@app.command()
def llm_check(config: ConfigOption = None) -> None:
    """Verify that the configured OpenAI-compatible LLM API is reachable."""
    sample = (
        "Dearest gentle codexer. We did a sneaky double reset. "
        "Not only do you get a full reset on us. But you are also getting one into the reset bank."
    )
    cfg = load_config(config)
    cfg.classifier.mode = "llm"
    item = RawItem(
        source=SourceKind.FIXTURE,
        source_id="llm-check",
        author="thsottiaux",
        text=sample,
        created_at=datetime.now(timezone.utc),
    )
    event = asyncio.run(WatcherRunner(cfg).classify(item))
    console.print(event_to_json_line(event))


@app.command()
def email_check(
    to: Annotated[str | None, typer.Option("--to", help="Override EMAIL_TO for this test.")] = None,
    config: ConfigOption = None,
) -> None:
    """Send a test notification through the email channel."""
    cfg = load_config(config)
    cfg.notify.channels = ["email"]
    if to:
        import os

        os.environ[cfg.notify.email_to_env] = to
    event = ResetEvent(
        source=SourceKind.FIXTURE,
        source_id="email-check",
        author="thsottiaux",
        text=(
            "Email check: Dearest gentle codexer. We did a sneaky double reset. "
            "This is a test notification from tibo-codex-reset-watcher."
        ),
        created_at=datetime.now(timezone.utc),
        event_type=EventType.EXPLICIT_RESET,
        confidence=1.0,
        severity=Severity.HIGH,
        effective_time=datetime.now(timezone.utc),
        evidence=["email check", "explicit_reset"],
        reason="Manual email notification test.",
    )
    delivered = asyncio.run(WatcherRunner(cfg).notify(event))
    if not delivered:
        raise typer.Exit(code=1)
    console.print("Email test notification sent.")


@app.command()
def run_once(
    source: Annotated[str, typer.Option(help="Source to fetch: x or github.")] = "x",
    config: ConfigOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Classify without storing or notifying.")] = False,
) -> None:
    """Fetch one batch, classify, store, and notify."""
    cfg = load_config(config)
    result = asyncio.run(WatcherRunner(cfg).run_once(source, dry_run=dry_run))
    print_run_result(result, dry_run=dry_run)


@app.command()
def watch(
    source: Annotated[str, typer.Option(help="Source to fetch: x or github.")] = "x",
    interval: Annotated[int, typer.Option(help="Seconds between checks.")] = 600,
    config: ConfigOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Classify without storing or notifying.")] = False,
) -> None:
    """Continuously fetch and classify at a fixed interval."""
    cfg = load_config(config)
    runner = WatcherRunner(cfg)
    console.print(f"Watching {source} every {interval}s. Press Ctrl-C to stop.")
    try:
        while True:
            try:
                result = asyncio.run(runner.run_once(source, dry_run=dry_run))
                print_run_result(result, dry_run=dry_run)
            except Exception as exc:
                console.print(f"[red]Watch iteration failed[/red]: {exc}")
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("Stopped.")


@app.command()
def replay(
    path: Annotated[Path, typer.Argument(help="JSONL fixture file to replay.")],
    config: ConfigOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run/--store", help="Classify without storing or notifying.")] = True,
) -> None:
    """Replay a JSONL file containing raw public-signal items."""
    cfg = load_config(config)
    items = [raw_item_from_json(line, index) for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()) if line.strip()]
    result = asyncio.run(WatcherRunner(cfg).process_items(items, dry_run=dry_run))
    print_run_result(result, dry_run=dry_run)
    for event in result.events:
        console.print(event_to_json_line(event))


@app.command()
def init_config(
    path: Annotated[Path, typer.Argument(help="Where to write the example config.")] = Path("config.example.yml"),
) -> None:
    """Write an example config file."""
    if path.exists():
        raise typer.BadParameter(f"{path} already exists; choose another path.")
    path.write_text(EXAMPLE_CONFIG, encoding="utf-8")
    console.print(f"Wrote {path}")


def parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def raw_item_from_json(line: str, index: int) -> RawItem:
    data = json.loads(line)
    source = SourceKind(data.get("source", "fixture"))
    created_raw = data.get("created_at")
    created_at = parse_dt(created_raw) if created_raw else datetime.now(timezone.utc)
    return RawItem(
        source=source,
        source_id=str(data.get("source_id") or data.get("id") or f"fixture-{index}"),
        author=str(data.get("author", "thsottiaux")),
        text=str(data["text"]),
        created_at=created_at,
        url=data.get("url"),
        metadata=data.get("metadata", {}),
    )


def print_run_result(result, dry_run: bool = False) -> None:
    console.print(
        {
            "fetched": result.fetched,
            "new_items": result.new_items,
            "events": len(result.events),
            "stored": result.stored,
            "notified": result.notified,
            "dry_run": dry_run,
        }
    )


EXAMPLE_CONFIG = """\
x:
  bearer_token_env: X_BEARER_TOKEN
  username: thsottiaux
  max_results: 20

github:
  token_env: GITHUB_TOKEN
  repo: openai/codex
  max_results: 20

classifier:
  mode: rules  # rules | hybrid | llm
  candidate_score: 0.55
  notify_score: 0.80

llm:
  provider: openai-compatible
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
  base_url: https://api.openai.com/v1

notify:
  channels:
    - console
  min_level: medium
  timezone: Asia/Shanghai
  jsonl_path: events.jsonl

storage:
  sqlite_path: watcher.sqlite3
"""


if __name__ == "__main__":
    app()
