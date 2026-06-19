# tibo-codex-reset-watcher

A small public-signal watcher for detecting Tibo-style Codex rate-limit reset hints and announcements.

It watches public sources, classifies explicit and implicit Codex reset signals, extracts likely effective reset times, stores events locally, and sends notifications.

This project is not affiliated with OpenAI. It uses public signals only and provides best-effort detection.

## Why

Codex reset announcements are sometimes direct:

```text
I have reset usage limits for Codex across all paid plans.
```

Sometimes they are more hint-shaped:

```text
This was fixed. You know what's coming 👀

Give us 24 hours to reset the Codex rate limits across all plans.
```

This tool turns those public signals into structured events.

## Features

- Local rule classifier by default, no LLM required.
- Explicit reset, scheduled reset, implicit reset, and weak-hint detection.
- Effective-time extraction for phrases like `give us 24 hours`.
- SQLite storage and de-duplication.
- Console and JSONL notifications.
- Optional Telegram and Discord notifications.
- Optional OpenAI-compatible LLM classifier with the user's own API key.
- Optional GitHub source for `openai/codex` rate-limit feature changes.

## Install

Use `uv` or a conda environment. For example:

```bash
conda activate gen
uv pip install .
```

For development:

```bash
conda activate gen
uv pip install -e ".[dev]"
uv run --extra dev pytest
```

You can also build and install the wheel:

```bash
uv build
uv pip install dist/*.whl
```

## Quick Start

Classify one text sample locally:

```bash
tibo-reset-watch classify-text "Give us 24 hours to reset the Codex rate limits across all plans."
```

Classify one text sample with your configured LLM API:

```bash
export OPENAI_API_KEY="..."
tibo-reset-watch classify-text "Dearest gentle codexer. We did a sneaky double reset." --mode llm --config config.yml
```

Check whether the configured LLM API is reachable:

```bash
tibo-reset-watch llm-check --config config.yml
```

Create a config file:

```bash
tibo-reset-watch init-config config.yml
```

Run one X API fetch:

```bash
export X_BEARER_TOKEN="..."
tibo-reset-watch run-once --source x --config config.yml
```

Run one GitHub commit search:

```bash
tibo-reset-watch run-once --source github --config config.yml
```

Replay local fixtures:

```bash
tibo-reset-watch replay examples/fixtures/tibo_posts.jsonl
```

Run continuously:

```bash
tibo-reset-watch watch --source x --interval 600 --config config.yml
```

## Configuration

See [config.example.yml](config.example.yml).

The default classifier mode is `rules`.

```yaml
classifier:
  mode: rules  # rules | hybrid | llm
```

LLM classification is optional. If enabled, candidate text and metadata are sent to your configured API provider.

```yaml
classifier:
  mode: hybrid

llm:
  provider: openai
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY
  # base_url is filled by the provider preset.
```

Provider presets:

```yaml
# DeepSeek
llm:
  provider: deepseek
  model: deepseek-v4-flash
  api_key_env: DEEPSEEK_API_KEY

# OpenRouter
llm:
  provider: openrouter
  model: deepseek/deepseek-chat-v3.1
  api_key_env: OPENROUTER_API_KEY
  extra_headers:
    HTTP-Referer: https://github.com/yourname/tibo-codex-reset-watcher
    X-Title: tibo-codex-reset-watcher

# LiteLLM or other gateway
llm:
  provider: openai-compatible
  model: your-model
  api_key_env: LITELLM_API_KEY
  base_url: http://localhost:4000/v1
  use_response_format: never
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

Check your LLM configuration:

```bash
export OPENAI_API_KEY="..."
tibo-reset-watch llm-check --config config.yml
```

Classify one sample with the LLM:

```bash
tibo-reset-watch classify-text \
  "Dearest gentle codexer. We did a sneaky double reset." \
  --mode llm \
  --config config.yml \
  --json
```

Use `hybrid` to let local rules screen candidates before calling the LLM:

```bash
tibo-reset-watch run-once --source x --config config.yml
```

```yaml
classifier:
  mode: hybrid
```

The LLM adapter uses the OpenAI-compatible Chat Completions endpoint:

```text
POST {base_url}/chat/completions
Authorization: Bearer $OPENAI_API_KEY
```

If a compatible provider does not support JSON response mode, the adapter retries without `response_format`.

## Notification Channels

Console is the safest default:

```yaml
notify:
  channels:
    - console
  min_level: medium
```

JSONL:

```yaml
notify:
  channels:
    - console
    - jsonl
  jsonl_path: events.jsonl
```

Telegram:

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

```yaml
notify:
  channels:
    - telegram
```

Discord:

```bash
export DISCORD_WEBHOOK_URL="..."
```

```yaml
notify:
  channels:
    - discord
```

Email via SMTP:

```bash
export EMAIL_SMTP_HOST="smtp.example.com"
export EMAIL_SMTP_PORT="587"
export EMAIL_USERNAME="your@email.com"
export EMAIL_PASSWORD="your_app_password"
export EMAIL_FROM="your@email.com"
export EMAIL_TO="destination@email.com"
export EMAIL_USE_TLS="true"
export EMAIL_USE_SSL="false"
```

```yaml
notify:
  channels:
    - email
```

For SMTP-over-SSL, commonly port `465`, use:

```bash
export EMAIL_USE_TLS="false"
export EMAIL_USE_SSL="true"
```

## Event Types

- `explicit_reset`: direct reset announcement.
- `scheduled_reset`: reset announced for a future window.
- `implicit_reset`: strong hint that reset is coming or happened.
- `weak_hint`: plausible but low-confidence hint.
- `rate_limit_change`: public source says limits or included usage changed.
- `rate_limit_feature_change`: GitHub signal about limit/reset mechanics.
- `incident_notice`: reliability or incident context.
- `unrelated`: no useful signal.

## Roadmap

- RSS/Atom output.
- GitHub Actions scheduled watcher example.
- Multi-account watchlist.
- More fixtures for Tibo-style phrasing.
- Small public dashboard.

## Development

```bash
uv run --extra dev pytest
```

If an editable development environment gets stale, reinstall the package:

```bash
uv pip install -e ".[dev]" --reinstall
```
