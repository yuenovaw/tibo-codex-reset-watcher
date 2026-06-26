# tibo-codex-reset-watcher

A lightweight watcher that monitors public signals for OpenAI Codex rate-limit reset announcements, classifies them, and sends notifications through your preferred channels.

It watches X (Twitter) posts and GitHub commits, classifies explicit and implicit reset signals, extracts likely effective reset times, stores events locally, and delivers notifications.

> **Disclaimer:** This project is not affiliated with OpenAI. It uses only publicly available signals and provides best-effort detection.

## How it works

Codex reset announcements range from direct:

```
I have reset usage limits for Codex across all paid plans.
```

to hint-shaped:

```
This was fixed. You know what's coming 👀
Give us 24 hours to reset the Codex rate limits across all plans.
```

The watcher turns those public signals into structured, deduplicated events.

## Features

- **Rule-based classifier** — works locally with no API key or external dependency
- **Signal types** — explicit reset, scheduled reset, implicit reset, weak hints, rate-limit changes, GitHub feature changes, and incident notices
- **Effective-time extraction** — parses phrases like "give us 24 hours" into timestamps
- **SQLite storage** with deduplication and notification tracking
- **Notification channels** — console, JSONL, Telegram, Discord, email (SMTP)
- **Optional LLM classifier** — uses any OpenAI-compatible API with your own key
- **Hybrid mode** — rules screen candidates first, LLM only runs on plausible hits

## Install

Requires Python 3.11+. Recommended with [`uv`](https://github.com/astral-sh/uv):

```bash
uv sync
uv run tibo-reset-watch --help
```

Or install into your current Python environment:

```bash
pip install .
```

For development:

```bash
uv sync --extra dev
uv run pytest
```

## Quick start

**Classify a single text sample (no API key needed):**

```bash
tibo-reset-watch classify-text "Give us 24 hours to reset the Codex rate limits across all plans."
```

**Replay bundled fixture posts:**

```bash
tibo-reset-watch replay examples/fixtures/tibo_posts.jsonl
```

**Run a one-shot X API fetch:**

```bash
export X_BEARER_TOKEN="..."
tibo-reset-watch run-once --source x --config config.yml
```

**Run continuously:**

```bash
tibo-reset-watch watch --source x --interval 600 --config config.yml
```

**Create a starter config:**

```bash
tibo-reset-watch init-config config.yml
```

## Configuration

Copy [`config.example.yml`](config.example.yml) and adjust as needed. The default classifier requires no external services:

```yaml
classifier:
  mode: rules  # rules | hybrid | llm
```

### LLM classifier (optional)

Any OpenAI-compatible provider works. Set `mode: hybrid` to run the LLM only on rule-screened candidates, reducing API calls:

```yaml
classifier:
  mode: hybrid

llm:
  provider: openai
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
```

Built-in provider presets (set `base_url` automatically):

| Provider | `provider` value |
|---|---|
| OpenAI | `openai` |
| DeepSeek | `deepseek` |
| OpenRouter | `openrouter` |
| LiteLLM | `litellm` |
| Ollama | `ollama` |
| Any other OpenAI-compatible | `openai-compatible` + `base_url` |

Check your LLM configuration:

```bash
export OPENAI_API_KEY="..."
tibo-reset-watch llm-check --config config.yml
```

Advanced LLM options:

```yaml
llm:
  use_response_format: auto  # auto | always | never
  temperature: 0
  timeout_seconds: 45
  max_retries: 2
  extra_headers: {}
  extra_body: {}
```

### Notification channels

**Console (default):**

```yaml
notify:
  channels:
    - console
  min_level: medium  # low | medium | high
```

**JSONL file:**

```yaml
notify:
  channels:
    - console
    - jsonl
  jsonl_path: events.jsonl
```

**Telegram:**

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

```yaml
notify:
  channels:
    - telegram
```

**Discord:**

```bash
export DISCORD_WEBHOOK_URL="..."
```

```yaml
notify:
  channels:
    - discord
```

**Email (SMTP):**

```bash
export EMAIL_SMTP_HOST="smtp.example.com"
export EMAIL_SMTP_PORT="587"
export EMAIL_USERNAME="you@example.com"
export EMAIL_PASSWORD="..."
export EMAIL_TO="destination@example.com"
export EMAIL_USE_TLS="true"
```

```yaml
notify:
  channels:
    - email
```

## Event types

| Type | Description |
|---|---|
| `explicit_reset` | Direct announcement that limits were reset |
| `scheduled_reset` | Reset announced for a future window |
| `implicit_reset` | Strong hint that a reset occurred or is coming |
| `weak_hint` | Plausible but low-confidence signal |
| `rate_limit_change` | Limits or included usage changed (not a reset) |
| `rate_limit_feature_change` | GitHub signal about limit/reset mechanics |
| `incident_notice` | Reliability or incident context |
| `unrelated` | No useful signal |

## Development

```bash
uv sync --extra dev
uv run pytest
```

## License

[MIT](LICENSE)
