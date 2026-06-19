from __future__ import annotations

from tibo_codex_reset_watcher.cli import raw_item_from_json
from typer.testing import CliRunner

from tibo_codex_reset_watcher.cli import app
from tibo_codex_reset_watcher.models import SourceKind

runner = CliRunner()


def test_raw_item_from_json() -> None:
    raw = raw_item_from_json(
        '{"source":"x","source_id":"abc","author":"thsottiaux","text":"Codex reset","created_at":"2026-06-19T12:00:00Z"}',
        0,
    )
    assert raw.source == SourceKind.X
    assert raw.source_id == "abc"
    assert raw.author == "thsottiaux"
    assert raw.created_at.isoformat() == "2026-06-19T12:00:00+00:00"


def test_classify_text_rules_mode() -> None:
    result = runner.invoke(
        app,
        [
            "classify-text",
            "Dearest gentle codexer. We did a sneaky double reset.",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert "explicit_reset" in result.stdout


def test_email_check_without_smtp_config_exits_nonzero() -> None:
    result = runner.invoke(app, ["email-check", "--to", "yuenovaw@foxmail.com"])
    assert result.exit_code == 1
