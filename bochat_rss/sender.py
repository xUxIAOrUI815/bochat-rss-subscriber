from __future__ import annotations

from dataclasses import dataclass

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
    parts = [f"【{item.source_name}】{item.title}"]
    if item.published_at:
        parts.append(f"发布时间：{item.published_at}")
    if item.link:
        parts.append(f"链接：{item.link}")
    if item.summary:
        summary = _compact_summary(item.summary)
        if summary:
            parts.append("")
            parts.append(summary)
    return "\n".join(parts)


def _compact_summary(summary: str, max_len: int = 500) -> str:
    text = " ".join(summary.split())
    if len(text) <= max_len:
        return text
    return f"{text[:max_len - 3]}..."
