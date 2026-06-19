from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import httpx

from tibo_codex_reset_watcher.config import LLMConfig
from tibo_codex_reset_watcher.models import EventType, RawItem, ResetEvent, Severity


SYSTEM_PROMPT = """You classify public posts about OpenAI Codex usage limits.

Return JSON only.

A reset event means the author announces that Codex usage limits, rate limits, tokens, or paid-plan quotas have been reset or will be reset.

Recognize both explicit reset announcements and Tibo-style hints such as "you know what's coming", "may the tokens flow again", or "give us 24 hours", but do not classify ordinary product updates, model releases, CLI features, outages, or performance notes as reset events unless they imply resetting limits/usage/tokens.

Domain hints:
- "codexer" means a Codex user.
- "sneaky double reset" means a reset event.
- "full reset on us" means the user's Codex usage/rate limits were reset.
- "reset bank" means a reset credit or banked reset that the user can redeem later.
- A post can be a reset event even if it does not literally say "rate limits" or "usage limits", when it clearly says Codex users get a reset.
- "increased usage limits", "higher rate limits", or "more usage included" are rate_limit_change, not explicit_reset, unless the post also says limits were reset.

Allowed event_type values:
explicit_reset, implicit_reset, scheduled_reset, weak_hint, rate_limit_change, rate_limit_feature_change, incident_notice, unrelated.

Return this JSON shape:
{
  "event_type": "...",
  "confidence": 0.0,
  "effective_time": "ISO-8601 timestamp or null",
  "approximate_time": false,
  "evidence": ["short matched phrases"],
  "reason": "short explanation"
}

If the post says "I have reset" or "we have reset", effective_time is the post creation time.
If it says "give us 24 hours", effective_time is created_at + 24 hours.
If timing is vague, set approximate_time=true.
"""


class LLMClassifier:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    async def classify(self, item: RawItem, rule_event: ResetEvent | None = None) -> ResetEvent:
        api_key = self.config.api_key
        if not api_key:
            raise RuntimeError(f"Missing LLM API key env var: {self.config.api_key_env}")

        payload = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source": item.source.value,
                            "author": item.author,
                            "created_at": item.created_at.isoformat(),
                            "text": item.text,
                            "rule_event": rule_event.model_dump(mode="json") if rule_event else None,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        payload.update(self.config.extra_body)
        headers = {"Authorization": f"Bearer {api_key}", **self.config.extra_headers}
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        if self.config.use_response_format in {"auto", "always"}:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await self._post_with_retries(client, url, headers, payload)
            if response.status_code == 400 and self.config.use_response_format == "auto":
                payload.pop("response_format", None)
                response = await self._post_with_retries(client, url, headers, payload)
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = parse_llm_json(content)
        return llm_json_to_event(item, data)

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        response: httpx.Response | None = None
        attempts = max(1, self.config.max_retries + 1)
        for attempt in range(attempts):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError:
                if attempt == attempts - 1:
                    raise
                continue
            if response.status_code not in {408, 429, 500, 502, 503, 504} or attempt == attempts - 1:
                return response
        assert response is not None
        return response


def llm_json_to_event(item: RawItem, data: dict[str, Any]) -> ResetEvent:
    event_type = parse_event_type(data.get("event_type", "unrelated"))
    confidence = float(data.get("confidence", default_confidence(event_type)))
    severity = severity_from_event(event_type, confidence)
    effective_raw = data.get("effective_time")
    effective_time = datetime.fromisoformat(effective_raw.replace("Z", "+00:00")) if effective_raw else None
    return ResetEvent(
        source=item.source,
        source_id=item.source_id,
        author=item.author,
        source_url=item.url,
        text=item.text,
        created_at=item.created_at,
        event_type=event_type,
        confidence=max(0.0, min(confidence, 1.0)),
        severity=severity,
        effective_time=effective_time,
        approximate_time=bool(data.get("approximate_time", False)),
        evidence=list(data.get("evidence", [])),
        reason=str(data.get("reason", "LLM classification")),
    )


def parse_llm_json(content: str) -> dict[str, Any]:
    text = content.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON must be an object.")
    return parsed


def parse_event_type(value: Any) -> EventType:
    try:
        return EventType(str(value))
    except ValueError:
        return EventType.UNRELATED


def severity_from_event(event_type: EventType, confidence: float) -> Severity:
    if event_type in {EventType.EXPLICIT_RESET, EventType.SCHEDULED_RESET} and confidence >= 0.75:
        return Severity.HIGH
    if event_type == EventType.IMPLICIT_RESET and confidence >= 0.65:
        return Severity.MEDIUM
    if event_type in {EventType.WEAK_HINT, EventType.RATE_LIMIT_CHANGE, EventType.RATE_LIMIT_FEATURE_CHANGE}:
        return Severity.LOW
    return Severity.NONE


def default_confidence(event_type: EventType) -> float:
    if event_type in {EventType.EXPLICIT_RESET, EventType.SCHEDULED_RESET}:
        return 0.85
    if event_type == EventType.IMPLICIT_RESET:
        return 0.70
    if event_type in {EventType.WEAK_HINT, EventType.RATE_LIMIT_CHANGE, EventType.RATE_LIMIT_FEATURE_CHANGE}:
        return 0.60
    return 0.0
