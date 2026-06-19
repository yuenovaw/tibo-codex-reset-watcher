from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from tibo_codex_reset_watcher.config import AppConfig
from tibo_codex_reset_watcher.models import RawItem, SourceKind
from tibo_codex_reset_watcher.runner import WatcherRunner


def raw_item(source_id: str = "1") -> RawItem:
    return RawItem(
        source=SourceKind.X,
        source_id=source_id,
        author="thsottiaux",
        text="I have reset usage limits for Codex across all paid plans.",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url=f"https://x.com/thsottiaux/status/{source_id}",
    )


def test_process_items_does_not_notify_same_event_twice(tmp_path) -> None:
    config = AppConfig()
    config.storage.sqlite_path = tmp_path / "watcher.sqlite3"
    config.notify.channels = ["jsonl"]
    config.notify.jsonl_path = tmp_path / "events.jsonl"
    runner = WatcherRunner(config)

    first = asyncio.run(runner.process_items([raw_item()]))
    second = asyncio.run(runner.process_items([raw_item()]))

    assert first.notified == 1
    assert second.notified == 0


def test_notification_channel_failure_does_not_block_successful_channel(tmp_path) -> None:
    config = AppConfig()
    config.storage.sqlite_path = tmp_path / "watcher.sqlite3"
    config.notify.channels = ["telegram", "jsonl"]
    config.notify.jsonl_path = tmp_path / "events.jsonl"
    runner = WatcherRunner(config)

    result = asyncio.run(runner.process_items([raw_item("2")]))

    assert result.notified == 1
    assert config.notify.jsonl_path.exists()


def test_email_channel_failure_does_not_block_successful_channel(tmp_path) -> None:
    config = AppConfig()
    config.storage.sqlite_path = tmp_path / "watcher.sqlite3"
    config.notify.channels = ["email", "jsonl"]
    config.notify.jsonl_path = tmp_path / "events.jsonl"
    runner = WatcherRunner(config)

    result = asyncio.run(runner.process_items([raw_item("3")]))

    assert result.notified == 1
    assert config.notify.jsonl_path.exists()
