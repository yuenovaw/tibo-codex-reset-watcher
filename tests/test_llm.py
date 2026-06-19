from __future__ import annotations

from datetime import datetime, timezone

from tibo_codex_reset_watcher.classifier.llm import llm_json_to_event, parse_llm_json
from tibo_codex_reset_watcher.config import LLMConfig
from tibo_codex_reset_watcher.models import EventType, RawItem, SourceKind


def test_llm_json_to_event_parses_openai_compatible_response() -> None:
    item = RawItem(
        source=SourceKind.X,
        source_id="llm",
        author="thsottiaux",
        text="Give us 24 hours to reset the Codex rate limits across all plans.",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
        url="https://x.com/thsottiaux/status/llm",
    )
    event = llm_json_to_event(
        item,
        {
            "event_type": "scheduled_reset",
            "confidence": 0.94,
            "effective_time": "2026-06-20T12:00:00Z",
            "approximate_time": False,
            "evidence": ["give us 24 hours", "Codex rate limits"],
            "reason": "Scheduled reset announcement.",
        },
    )

    assert event.event_type == EventType.SCHEDULED_RESET
    assert event.confidence == 0.94
    assert event.effective_time == datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)


def test_llm_json_defaults_confidence_for_known_event_type() -> None:
    item = RawItem(
        source=SourceKind.X,
        source_id="llm",
        author="thsottiaux",
        text="We did a sneaky double reset.",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
    )
    event = llm_json_to_event(item, {"event_type": "explicit_reset"})
    assert event.confidence == 0.85
    assert event.severity.value == "high"


def test_llm_json_unknown_event_type_falls_back_to_unrelated() -> None:
    item = RawItem(
        source=SourceKind.X,
        source_id="llm",
        author="thsottiaux",
        text="hello",
        created_at=datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc),
    )
    event = llm_json_to_event(item, {"event_type": "surprise"})
    assert event.event_type == EventType.UNRELATED


def test_parse_llm_json_accepts_fenced_json() -> None:
    parsed = parse_llm_json(
        """Here you go:
```json
{"event_type":"explicit_reset","confidence":0.91}
```
"""
    )
    assert parsed["event_type"] == "explicit_reset"


def test_llm_provider_presets() -> None:
    deepseek = LLMConfig(provider="deepseek", model="deepseek-v4-flash", api_key_env="DEEPSEEK_API_KEY")
    assert deepseek.base_url == "https://api.deepseek.com/v1"
    assert deepseek.use_response_format == "auto"

    ollama = LLMConfig(provider="ollama", model="qwen2.5:7b", api_key_env="OLLAMA_API_KEY")
    assert ollama.base_url == "http://localhost:11434/v1"
    assert ollama.use_response_format == "never"
