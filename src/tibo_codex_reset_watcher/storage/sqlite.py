from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from tibo_codex_reset_watcher.models import RawItem, ResetEvent


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self) -> None:
        self.conn.execute("pragma journal_mode=wal")
        self.conn.executescript(
            """
            create table if not exists raw_items (
              source text not null,
              source_id text not null,
              author text not null,
              text text not null,
              created_at text not null,
              fetched_at text not null,
              url text,
              raw_json text not null,
              primary key (source, source_id)
            );

            create table if not exists events (
              id integer primary key autoincrement,
              source text not null,
              source_id text not null,
              event_type text not null,
              confidence real not null,
              severity text not null,
              effective_time text,
              approximate_time integer not null,
              notified_at text,
              raw_json text not null,
              unique (source, source_id, event_type)
            );
            """
        )
        self.conn.commit()

    def save_raw_item(self, item: RawItem) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            """
            insert or ignore into raw_items
              (source, source_id, author, text, created_at, fetched_at, url, raw_json)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.source.value,
                item.source_id,
                item.author,
                item.text,
                item.created_at.isoformat(),
                now,
                str(item.url) if item.url else None,
                item.model_dump_json(),
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def save_event(self, event: ResetEvent) -> bool:
        cursor = self.conn.execute(
            """
            insert or ignore into events
              (source, source_id, event_type, confidence, severity, effective_time,
               approximate_time, raw_json)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.source.value,
                event.source_id,
                event.event_type.value,
                event.confidence,
                event.severity.value,
                event.effective_time.isoformat() if event.effective_time else None,
                int(event.approximate_time),
                event.model_dump_json(),
            ),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def mark_notified(self, event: ResetEvent) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            update events set notified_at = ?
            where source = ? and source_id = ? and event_type = ?
            """,
            (now, event.source.value, event.source_id, event.event_type.value),
        )
        self.conn.commit()

    def event_already_notified(self, event: ResetEvent) -> bool:
        row = self.conn.execute(
            """
            select notified_at from events
            where source = ? and source_id = ? and event_type = ?
            """,
            (event.source.value, event.source_id, event.event_type.value),
        ).fetchone()
        return bool(row and row["notified_at"])

    def close(self) -> None:
        self.conn.close()


def event_to_json_line(event: ResetEvent) -> str:
    return json.dumps(event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)

