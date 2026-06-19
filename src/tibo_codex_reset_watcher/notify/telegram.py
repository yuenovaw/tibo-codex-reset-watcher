from __future__ import annotations

import httpx

from tibo_codex_reset_watcher.models import ResetEvent
from tibo_codex_reset_watcher.notify.text import render_plain_text


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, timezone: str = "Asia/Shanghai") -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timezone = timezone

    async def notify(self, event: ResetEvent) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": render_plain_text(event, self.timezone),
                    "disable_web_page_preview": False,
                },
            )
            response.raise_for_status()

