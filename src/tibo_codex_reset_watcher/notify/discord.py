from __future__ import annotations

import httpx

from tibo_codex_reset_watcher.models import ResetEvent
from tibo_codex_reset_watcher.notify.text import render_plain_text


class DiscordNotifier:
    def __init__(self, webhook_url: str, timezone: str = "Asia/Shanghai") -> None:
        self.webhook_url = webhook_url
        self.timezone = timezone

    async def notify(self, event: ResetEvent) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.webhook_url,
                json={"content": render_plain_text(event, self.timezone)},
            )
            response.raise_for_status()

