from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from tibo_codex_reset_watcher.config import XConfig
from tibo_codex_reset_watcher.models import RawItem, SourceKind


class XApiSource:
    def __init__(self, config: XConfig) -> None:
        self.config = config

    async def fetch(self) -> list[RawItem]:
        token = self.config.bearer_token
        if not token:
            raise RuntimeError(f"Missing X bearer token env var: {self.config.bearer_token_env}")

        params: dict[str, Any] = {
            "query": self.config.query,
            "max_results": self.config.max_results,
            "tweet.fields": "created_at,author_id,conversation_id",
        }
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get("https://api.x.com/2/tweets/search/recent", params=params, headers=headers)
            response.raise_for_status()
        payload = response.json()
        return [self._to_raw_item(row) for row in payload.get("data", [])]

    def _to_raw_item(self, row: dict[str, Any]) -> RawItem:
        tweet_id = str(row["id"])
        return RawItem(
            source=SourceKind.X,
            source_id=tweet_id,
            author=self.config.username,
            text=row["text"],
            created_at=datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")),
            url=f"https://x.com/{self.config.username}/status/{tweet_id}",
            metadata={k: v for k, v in row.items() if k not in {"id", "text", "created_at"}},
        )

