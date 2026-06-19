from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from tibo_codex_reset_watcher.extractors.time import extract_effective_time
from tibo_codex_reset_watcher.models import EventType, RawItem, ResetEvent, Severity, SourceKind


@dataclass(frozen=True)
class RuleHit:
    phrase: str
    weight: float
    category: str


class RuleClassifier:
    """Transparent first-pass classifier for Codex reset posts."""

    def __init__(
        self,
        hints_path: Path | None = None,
        notify_score: float = 0.80,
        candidate_score: float = 0.55,
    ) -> None:
        self.notify_score = notify_score
        self.candidate_score = candidate_score
        if hints_path is None:
            hints_path = Path(__file__).with_name("hints.yml")
        self.hints = yaml.safe_load(hints_path.read_text(encoding="utf-8"))

    def classify(self, item: RawItem) -> ResetEvent:
        text = normalize(item.text)
        hits = self._hits(text)
        score = min(sum(hit.weight for hit in hits), 1.0)
        event_type = self._event_type(hits, score, item.source)
        severity = self._severity(event_type, score)
        timing = extract_effective_time(item.text, item.created_at, event_type)
        evidence = [hit.phrase for hit in hits]

        return ResetEvent(
            source=item.source,
            source_id=item.source_id,
            author=item.author,
            source_url=item.url,
            text=item.text,
            created_at=item.created_at,
            event_type=event_type,
            confidence=round(score, 3),
            severity=severity,
            effective_time=timing.effective_time,
            approximate_time=timing.approximate,
            evidence=evidence,
            reason=build_reason(event_type, evidence, score),
        )

    def _hits(self, text: str) -> list[RuleHit]:
        hits: list[RuleHit] = []
        hits.extend(match_phrases(text, self.hints["context"], 0.25, "context", once=True))
        hits.extend(match_phrases(text, self.hints["explicit_reset"], 0.35, "explicit_reset"))
        hits.extend(match_phrases(text, self.hints["scheduled_reset"], 0.30, "scheduled_reset"))
        hits.extend(match_phrases(text, self.hints["implicit_strong"], 0.28, "implicit_strong"))
        hits.extend(match_phrases(text, self.hints["implicit_medium"], 0.12, "implicit_medium"))
        hits.extend(match_phrases(text, self.hints["feature_change"], 0.25, "feature_change"))
        hits.extend(match_phrases(text, self.hints["rate_limit_change"], 0.28, "rate_limit_change"))
        if "reset" in text:
            hits.append(RuleHit("reset", 0.20, "reset_word"))
        if "limits" in text or "tokens" in text:
            hits.append(RuleHit("limits/tokens", 0.18, "limits_word"))
        if "reset bank" in text:
            hits.append(RuleHit("reset bank", 0.20, "reset_credit"))
        if "across all plans" in text or "all paid plans" in text:
            hits.append(RuleHit("all plans", 0.20, "scope"))
        return dedupe_hits(hits)

    def _event_type(self, hits: list[RuleHit], score: float, source: SourceKind) -> EventType:
        categories = {hit.category for hit in hits}
        has_context = "context" in categories or "limits_word" in categories

        if source == SourceKind.GITHUB and "feature_change" in categories:
            return EventType.RATE_LIMIT_FEATURE_CHANGE
        if "rate_limit_change" in categories and has_context:
            return EventType.RATE_LIMIT_CHANGE
        if not has_context and score < self.notify_score:
            return EventType.UNRELATED
        if "scheduled_reset" in categories and ("explicit_reset" in categories or "reset_word" in categories):
            return EventType.SCHEDULED_RESET
        if "explicit_reset" in categories and has_context:
            return EventType.EXPLICIT_RESET
        if "implicit_strong" in categories and has_context and score >= self.candidate_score:
            return EventType.IMPLICIT_RESET
        if {"implicit_medium", "context"} <= categories and score >= 0.45:
            return EventType.WEAK_HINT
        if "incident" in " ".join(hit.phrase for hit in hits) and has_context:
            return EventType.INCIDENT_NOTICE
        return EventType.UNRELATED

    def _severity(self, event_type: EventType, score: float) -> Severity:
        if event_type in {EventType.EXPLICIT_RESET, EventType.SCHEDULED_RESET} and score >= self.notify_score:
            return Severity.HIGH
        if event_type == EventType.IMPLICIT_RESET and score >= self.candidate_score:
            return Severity.MEDIUM
        if event_type in {EventType.WEAK_HINT, EventType.RATE_LIMIT_CHANGE, EventType.RATE_LIMIT_FEATURE_CHANGE}:
            return Severity.LOW
        return Severity.NONE


def normalize(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())


def match_phrases(
    text: str,
    phrases: Iterable[str],
    weight: float,
    category: str,
    once: bool = False,
) -> list[RuleHit]:
    hits = []
    matched_phrases: list[str] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        normalized = normalize(phrase)
        if any(normalized in matched for matched in matched_phrases):
            continue
        if normalized in text:
            hits.append(RuleHit(phrase, weight, category))
            matched_phrases.append(normalized)
            if once:
                break
    return hits


def dedupe_hits(hits: list[RuleHit]) -> list[RuleHit]:
    seen: set[tuple[str, str]] = set()
    seen_phrases: set[str] = set()
    result = []
    for hit in hits:
        phrase_key = hit.phrase.casefold()
        key = (phrase_key, hit.category)
        if key not in seen and phrase_key not in seen_phrases:
            result.append(hit)
            seen.add(key)
            seen_phrases.add(phrase_key)
    return remove_subphrase_hits(result)


def remove_subphrase_hits(hits: list[RuleHit]) -> list[RuleHit]:
    result: list[RuleHit] = []
    normalized = [(hit, normalize(hit.phrase)) for hit in hits]
    for hit, phrase in normalized:
        is_subphrase = any(
            hit.category == other.category
            and phrase != other_phrase
            and phrase in other_phrase
            for other, other_phrase in normalized
        )
        if not is_subphrase:
            result.append(hit)
    return result


def build_reason(event_type: EventType, evidence: list[str], score: float) -> str:
    if event_type == EventType.UNRELATED:
        return "No reset-related signal crossed the rule threshold."
    return f"Matched {event_type.value} with score {score:.2f}: {', '.join(evidence)}"
