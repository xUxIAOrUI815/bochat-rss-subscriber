from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
from typing import Any


class StateError(RuntimeError):
    pass


@dataclass
class FeedState:
    seen: list[str] = field(default_factory=list)
    last_checked_at: str | None = None


class RssState:
    def __init__(self, path: Path, feeds: dict[str, FeedState] | None = None):
        self.path = path
        self.feeds = feeds or {}

    @classmethod
    def load(cls, path: str | Path) -> "RssState":
        state_path = Path(path)
        if not state_path.exists():
            return cls(state_path)
        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise StateError(f"状态文件 JSON 格式错误: {state_path}") from exc

        feeds_raw = raw.get("feeds", {}) if isinstance(raw, dict) else {}
        feeds: dict[str, FeedState] = {}
        if isinstance(feeds_raw, dict):
            for feed_id, feed_raw in feeds_raw.items():
                if not isinstance(feed_raw, dict):
                    continue
                seen = feed_raw.get("seen", [])
                feeds[str(feed_id)] = FeedState(
                    seen=[str(item) for item in seen] if isinstance(seen, list) else [],
                    last_checked_at=feed_raw.get("last_checked_at"),
                )
        return cls(state_path, feeds)

    def is_feed_initialized(self, feed_id: str) -> bool:
        return feed_id in self.feeds

    def has_seen(self, feed_id: str, key: str) -> bool:
        return key in self._feed(feed_id).seen

    def mark_seen(self, feed_id: str, key: str, max_seen: int = 1000) -> None:
        feed = self._feed(feed_id)
        if key in feed.seen:
            feed.seen.remove(key)
        feed.seen.append(key)
        if len(feed.seen) > max_seen:
            del feed.seen[: len(feed.seen) - max_seen]

    def mark_checked(self, feed_id: str) -> None:
        self._feed(feed_id).last_checked_at = datetime.now(timezone.utc).isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "feeds": {
                feed_id: {
                    "seen": feed_state.seen,
                    "last_checked_at": feed_state.last_checked_at,
                }
                for feed_id, feed_state in sorted(self.feeds.items())
            }
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        ) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        os.replace(tmp_path, self.path)

    def _feed(self, feed_id: str) -> FeedState:
        if feed_id not in self.feeds:
            self.feeds[feed_id] = FeedState()
        return self.feeds[feed_id]
