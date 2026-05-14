from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

from bochat_sdk import BochatClient

from .config import AppConfig, FeedConfig
from .rss import RssItem


@dataclass(frozen=True)
class SendResult:
    msg_id: int | None = None
    dry_run: bool = False


class BoChatSender:
    def __init__(self, config: AppConfig):
        self._client = BochatClient.builder(config.base_url).bot_token(config.bot_token).build()

    async def close(self) -> None:
        await self._client.close()

    async def send_item(self, feed: FeedConfig, item: RssItem) -> SendResult:
        message = format_item_message(item)
        response = await self._client.messages().send_text(feed.group_id, message)
        return SendResult(msg_id=response.msg_id)


class DryRunSender:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    async def close(self) -> None:
        return None

    async def send_item(self, feed: FeedConfig, item: RssItem) -> SendResult:
        message = format_item_message(item)
        self.messages.append((feed.group_id, message))
        print(f"[dry-run] group={feed.group_id}\n{message}\n")
        return SendResult(dry_run=True)


def format_item_message(item: RssItem) -> str:
    title = item.title.strip() or "(untitled)"
    if item.link:
        parts = [f"### [{title}]({item.link})"]
    else:
        parts = [f"### {title}"]

    parts.append(f"**来源**：{item.source_name}")
    if item.published_at:
        parts.append(f"**发布时间**：{_format_published_at(item.published_at)}")
    if item.summary:
        summary = _compact_summary(item.summary)
        if summary:
            parts.append("")
            parts.append(summary)
    return "\n".join(parts)


def _compact_summary(summary: str, max_len: int = 500) -> str:
    text = " ".join(_strip_html(summary).split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len - 3]}..."


def _format_published_at(value: str) -> str:
    text = value.strip()
    parsed = _parse_datetime(text)
    if parsed is None:
        return text

    formatted = parsed.strftime("%Y-%m-%d %H:%M")
    if parsed.tzinfo is None:
        return formatted

    offset = parsed.utcoffset()
    if offset is None:
        return formatted
    if offset.total_seconds() == 0:
        return f"{formatted} UTC"

    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{formatted} UTC{sign}{hours:02d}:{minutes:02d}"


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _strip_html(value: str) -> str:
    parser = _HtmlTextExtractor()
    parser.feed(value)
    parser.close()
    return parser.text()


class _HtmlTextExtractor(HTMLParser):
    _BREAK_TAGS = {
        "address",
        "article",
        "br",
        "dd",
        "div",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BREAK_TAGS:
            self._parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BREAK_TAGS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)
