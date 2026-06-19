from __future__ import annotations

from zoneinfo import ZoneInfo

from tibo_codex_reset_watcher.models import ResetEvent


def render_plain_text(event: ResetEvent, timezone: str = "Asia/Shanghai") -> str:
    lines = [
        "Codex Reset Watcher",
        "",
        f"Type: {event.event_type.value}",
        f"Severity: {event.severity.value}",
        f"Confidence: {event.confidence:.0%}",
        f"Author: @{event.author}",
    ]
    if event.effective_time:
        local = event.effective_time.astimezone(ZoneInfo(timezone))
        suffix = " approx" if event.approximate_time else ""
        lines.append(f"Effective: {local.isoformat()}{suffix}")
    if event.evidence:
        lines.append(f"Evidence: {', '.join(event.evidence[:6])}")
    if event.source_url:
        lines.append(f"Source: {event.source_url}")
    lines.extend(["", event.text])
    return "\n".join(lines)

