from __future__ import annotations

from pathlib import Path

from tibo_codex_reset_watcher.models import ResetEvent
from tibo_codex_reset_watcher.storage.sqlite import event_to_json_line


class JsonlNotifier:
    def __init__(self, path: Path) -> None:
        self.path = path

    def notify(self, event: ResetEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(event_to_json_line(event))
            handle.write("\n")

