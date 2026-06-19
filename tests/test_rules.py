from __future__ import annotations

from datetime import datetime, timezone

from tibo_codex_reset_watcher.classifier.rules import RuleClassifier
from tibo_codex_reset_watcher.models import EventType, RawItem, SourceKind


def item(text: str) -> RawItem:
    return RawItem(
        source=SourceKind.X,
        source_id="1",
        author="thsottiaux",
        text=text,
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url="https://x.com/thsottiaux/status/1",
    )


def test_scheduled_reset_24h() -> None:
    event = RuleClassifier().classify(
        item("This was fixed. You know what's coming 👀 Give us 24 hours to reset the Codex rate limits across all plans.")
    )
    assert event.event_type == EventType.SCHEDULED_RESET
    assert event.effective_time == datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    assert event.confidence >= 0.8


def test_explicit_reset() -> None:
    event = RuleClassifier().classify(
        item("I have reset usage limits for Codex across all paid plans. May the tokens flow again.")
    )
    assert event.event_type == EventType.EXPLICIT_RESET
    assert event.effective_time == datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
    assert event.confidence >= 0.8


def test_weak_hint_without_context_is_unrelated() -> None:
    event = RuleClassifier().classify(item("This was fixed. You know what's coming 👀"))
    assert event.event_type == EventType.UNRELATED


def test_github_feature_change() -> None:
    github_item = RawItem(
        source=SourceKind.GITHUB,
        source_id="sha",
        author="dev",
        text="feat(app-server): expose rate-limit reset credits and account/rateLimits",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url="https://github.com/openai/codex/commit/sha",
    )
    event = RuleClassifier().classify(github_item)
    assert event.event_type == EventType.RATE_LIMIT_FEATURE_CHANGE


def test_implicit_reset_with_context() -> None:
    event = RuleClassifier().classify(
        item("Codex reliability is back where it should be. You know what's coming. May the tokens flow again.")
    )
    assert event.event_type == EventType.IMPLICIT_RESET


def test_evidence_skips_duplicate_subphrases() -> None:
    event = RuleClassifier().classify(
        item("Codex reliability is back where it should be. You know what's coming.")
    )
    assert "you know what's coming" in event.evidence
    assert "what's coming" not in event.evidence


def test_double_reset_and_reset_bank() -> None:
    event = RuleClassifier().classify(
        item(
            "Dearest gentle codexer.\n\n"
            "We did a sneaky double reset. Not only do you get a full reset on us. "
            "But you are also getting one into the reset bank to use at your own leisure."
        )
    )
    assert event.event_type == EventType.EXPLICIT_RESET
    assert event.severity.value == "high"
    assert event.effective_time == datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)


def test_x_usage_limit_increase_is_rate_limit_change() -> None:
    event = RuleClassifier().classify(
        item(
            "We gave gpt-5-codex a small sibling, you can now try gpt-5-codex-mini in Codex. "
            "Smaller, so up to 4X more usage included. Also increased usage limits by 50% for Plus, Edu and Team plans."
        )
    )
    assert event.event_type == EventType.RATE_LIMIT_CHANGE
    assert event.severity.value == "low"
