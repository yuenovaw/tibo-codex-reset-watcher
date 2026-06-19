from __future__ import annotations

from zoneinfo import ZoneInfo

from rich.console import Console
from rich.panel import Panel

from tibo_codex_reset_watcher.models import ResetEvent


class ConsoleNotifier:
    def __init__(self, timezone: str = "Asia/Shanghai") -> None:
        self.console = Console()
        self.timezone = ZoneInfo(timezone)

    def notify(self, event: ResetEvent) -> None:
        body = [
            f"Type: {event.event_type.value}",
            f"Severity: {event.severity.value}",
            f"Confidence: {event.confidence:.0%}",
            f"Author: @{event.author}",
        ]
        if event.effective_time:
            local_time = event.effective_time.astimezone(self.timezone)
            suffix = " approx" if event.approximate_time else ""
            body.append(f"Effective: {local_time.isoformat()}{suffix}")
        if event.evidence:
            body.append(f"Evidence: {', '.join(event.evidence[:6])}")
        if event.source_url:
            body.append(f"Source: {event.source_url}")
        body.append("")
        body.append(event.text)
        self.console.print(Panel("\n".join(body), title="Codex Reset Watcher"))

