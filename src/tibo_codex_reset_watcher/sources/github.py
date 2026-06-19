from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

from tibo_codex_reset_watcher.config import GitHubConfig
from tibo_codex_reset_watcher.models import RawItem, SourceKind


class GitHubSource:
    def __init__(self, config: GitHubConfig) -> None:
        self.config = config

    async def fetch_commits(self) -> list[RawItem]:
        owner_repo = self.config.repo
        query = f"repo:{owner_repo} {self.config.query}"
        url = f"https://api.github.com/search/commits?q={quote_plus(query)}&per_page={self.config.max_results}"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
        payload = response.json()
        return [self._commit_to_raw_item(row) for row in payload.get("items", [])]

    def _commit_to_raw_item(self, row: dict[str, Any]) -> RawItem:
        commit = row["commit"]
        created = commit.get("committer", {}).get("date") or commit.get("author", {}).get("date")
        created_at = (
            datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created
            else datetime.now(timezone.utc)
        )
        return RawItem(
            source=SourceKind.GITHUB,
            source_id=row["sha"],
            author=commit.get("author", {}).get("name") or "unknown",
            text=commit.get("message", ""),
            created_at=created_at,
            url=row.get("html_url"),
            metadata={"repo": self.config.repo},
        )

