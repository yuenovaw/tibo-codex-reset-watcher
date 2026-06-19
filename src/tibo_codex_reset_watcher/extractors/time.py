from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from tibo_codex_reset_watcher.models import EventType


@dataclass(frozen=True)
class TimeExtraction:
    effective_time: datetime | None
    approximate: bool = False


def extract_effective_time(text: str, created_at: datetime, event_type: EventType) -> TimeExtraction:
    text_norm = " ".join(text.casefold().replace("’", "'").split())
    created_at = ensure_utc(created_at)

    if event_type == EventType.UNRELATED:
        return TimeExtraction(None, False)

    if "give us 24 hours" in text_norm or "within 24 hours" in text_norm or "in 24 hours" in text_norm:
        return TimeExtraction(created_at + timedelta(hours=24), False)
    if "later today" in text_norm:
        end_of_day = created_at.replace(hour=23, minute=59, second=0, microsecond=0)
        return TimeExtraction(end_of_day, True)
    if "tomorrow" in text_norm:
        return TimeExtraction(created_at + timedelta(days=1), True)
    if event_type in {EventType.EXPLICIT_RESET, EventType.IMPLICIT_RESET, EventType.WEAK_HINT}:
        return TimeExtraction(created_at, event_type != EventType.EXPLICIT_RESET)
    return TimeExtraction(None, False)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

