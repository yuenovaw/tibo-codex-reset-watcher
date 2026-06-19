from __future__ import annotations

from datetime import datetime, timezone

from tibo_codex_reset_watcher.classifier.rules import RuleClassifier
from tibo_codex_reset_watcher.models import RawItem, SourceKind
from tibo_codex_reset_watcher.storage import SQLiteStore


def test_store_dedupes_raw_items_and_events(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "watcher.sqlite3")
    raw = RawItem(
        source=SourceKind.X,
        source_id="1",
        author="thsottiaux",
        text="Give us 24 hours to reset the Codex rate limits across all plans.",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url="https://x.com/thsottiaux/status/1",
    )
    event = RuleClassifier().classify(raw)

    assert store.save_raw_item(raw) is True
    assert store.save_raw_item(raw) is False
    assert store.save_event(event) is True
    assert store.save_event(event) is False
    assert store.event_already_notified(event) is False
    store.mark_notified(event)
    assert store.event_already_notified(event) is True
    store.close()


def test_notified_event_is_detected_after_reopen(tmp_path) -> None:
    db_path = tmp_path / "watcher.sqlite3"
    raw = RawItem(
        source=SourceKind.X,
        source_id="1",
        author="thsottiaux",
        text="I have reset usage limits for Codex across all paid plans.",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url="https://x.com/thsottiaux/status/1",
    )
    event = RuleClassifier().classify(raw)

    first = SQLiteStore(db_path)
    first.save_event(event)
    first.mark_notified(event)
    first.close()

    second = SQLiteStore(db_path)
    assert second.save_event(event) is False
    assert second.event_already_notified(event) is True
    second.close()
