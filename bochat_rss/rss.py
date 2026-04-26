from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import calendar
from pathlib import Path
import hashlib
import time
from typing import Any
from urllib.request import Request, urlopen

import feedparser

from .config import FeedConfig


class RssError(RuntimeError):
    pass


@dataclass(frozen=True)
class RssItem:
    feed_id: str
    source_name: str
    key: str
    title: str
    link: str | None
    summary: str | None
    published_at: str | None


def make_item_key(entry: Any) -> str:
    raw_key = (
        _entry_value(entry, "id")
        or _entry_value(entry, "guid")
        or _entry_value(entry, "link")
        or "|".join(
            value
            for value in [
                _entry_value(entry, "title"),
                _published_iso(entry),
            ]
            if value
        )
    )
    if not raw_key:
        raw_key = repr(entry)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def parse_feed_content(content: bytes | str, feed: FeedConfig) -> list[RssItem]:
    parsed = feedparser.parse(content)
    if getattr(parsed, "bozo", False):
        raise RssError(f"RSS 解析失败: {getattr(parsed, 'bozo_exception', 'unknown error')}")

    items: list[RssItem] = []
    for entry in getattr(parsed, "entries", []):
        title = _entry_value(entry, "title") or "(untitled)"
        items.append(
            RssItem(
                feed_id=feed.id,
                source_name=feed.name,
                key=make_item_key(entry),
                title=title,
                link=_entry_value(entry, "link"),
                summary=_entry_value(entry, "summary") or _entry_value(entry, "description"),
                published_at=_published_iso(entry),
            )
        )
    return items


def fetch_feed(feed: FeedConfig, timeout_secs: int = 20) -> list[RssItem]:
    if feed.url.startswith("file://"):
        content = Path(feed.url.removeprefix("file://")).read_bytes()
        return parse_feed_content(content, feed)

    request = Request(feed.url, headers={"User-Agent": "bochat-rss-subscriber/0.1.0"})
    try:
        with urlopen(request, timeout=timeout_secs) as response:
            content = response.read()
    except Exception as exc:
        raise RssError(f"RSS 拉取失败: {feed.id}: {exc}") from exc
    return parse_feed_content(content, feed)


def sort_items_old_to_new(items: list[RssItem]) -> list[RssItem]:
    return sorted(items, key=_sort_key)


def _sort_key(item: RssItem) -> tuple[float, str]:
    if item.published_at:
        try:
            return (datetime.fromisoformat(item.published_at).timestamp(), item.key)
        except ValueError:
            pass
    return (time.time(), item.key)


def _entry_value(entry: Any, key: str) -> str | None:
    value = None
    if isinstance(entry, dict):
        value = entry.get(key)
    else:
        value = getattr(entry, key, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _published_iso(entry: Any) -> str | None:
    parsed = None
    if isinstance(entry, dict):
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    else:
        parsed = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
    if parsed:
        try:
            timestamp = calendar.timegm(parsed)
        except Exception:
            timestamp = time.mktime(parsed)
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    return _entry_value(entry, "published") or _entry_value(entry, "updated")
