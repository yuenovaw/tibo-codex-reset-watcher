from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SourceKind(StrEnum):
    X = "x"
    GITHUB = "github"
    FIXTURE = "fixture"


class EventType(StrEnum):
    EXPLICIT_RESET = "explicit_reset"
    IMPLICIT_RESET = "implicit_reset"
    SCHEDULED_RESET = "scheduled_reset"
    WEAK_HINT = "weak_hint"
    RATE_LIMIT_CHANGE = "rate_limit_change"
    RATE_LIMIT_FEATURE_CHANGE = "rate_limit_feature_change"
    INCIDENT_NOTICE = "incident_notice"
    UNRELATED = "unrelated"


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class RawItem(BaseModel):
    source: SourceKind
    source_id: str
    author: str
    text: str
    created_at: datetime
    url: HttpUrl | str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResetEvent(BaseModel):
    source: SourceKind
    source_id: str
    author: str
    source_url: HttpUrl | str | None = None
    text: str
    created_at: datetime
    event_type: EventType
    confidence: float = Field(ge=0, le=1)
    severity: Severity
    effective_time: datetime | None = None
    approximate_time: bool = False
    evidence: list[str] = Field(default_factory=list)
    reason: str = ""

    @property
    def should_notify(self) -> bool:
        return self.severity in {Severity.HIGH, Severity.MEDIUM, Severity.LOW}
