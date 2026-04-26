from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Awaitable, Callable, Protocol

from .config import AppConfig, FeedConfig
from .rss import RssItem, fetch_feed, sort_items_old_to_new
from .sender import BoChatSender, DryRunSender
from .state import RssState


FetchFeed = Callable[[FeedConfig], list[RssItem]]


class Sender(Protocol):
    async def send_item(self, feed: FeedConfig, item: RssItem): ...
    async def close(self) -> None: ...


@dataclass(frozen=True)
class FeedCheckResult:
    feed_id: str
    fetched: int
    sent: int
    skipped_existing: int
    initialized_without_send: bool = False


async def latest_items(
    config: AppConfig,
    feed_id: str,
    limit: int = 5,
    fetcher: FetchFeed = fetch_feed,
) -> list[RssItem]:
    feed = find_feed(config, feed_id)
    items = await asyncio.to_thread(fetcher, feed)
    return sort_items_old_to_new(items)[-limit:]


async def check_all(
    config: AppConfig,
    dry_run: bool = False,
    fetcher: FetchFeed = fetch_feed,
    sender: Sender | None = None,
) -> list[FeedCheckResult]:
    state = RssState.load(config.state_path)
    owned_sender = sender is None
    sender = sender or (DryRunSender() if dry_run else BoChatSender(config))
    try:
        results = []
        for feed in config.enabled_feeds():
            results.append(await check_feed(config, feed.id, dry_run, fetcher, sender, state))
        return results
    finally:
        if owned_sender:
            await sender.close()


async def check_feed_by_id(
    config: AppConfig,
    feed_id: str,
    dry_run: bool = False,
    fetcher: FetchFeed = fetch_feed,
    sender: Sender | None = None,
) -> FeedCheckResult:
    state = RssState.load(config.state_path)
    owned_sender = sender is None
    sender = sender or (DryRunSender() if dry_run else BoChatSender(config))
    try:
        return await check_feed(config, feed_id, dry_run, fetcher, sender, state)
    finally:
        if owned_sender:
            await sender.close()


async def check_feed(
    config: AppConfig,
    feed_id: str,
    dry_run: bool,
    fetcher: FetchFeed,
    sender: Sender,
    state: RssState,
) -> FeedCheckResult:
    feed = find_feed(config, feed_id)
    items = sort_items_old_to_new(await asyncio.to_thread(fetcher, feed))
    initialized = state.is_feed_initialized(feed.id)

    if not initialized and not config.send_existing_on_first_run:
        for item in items:
            state.mark_seen(feed.id, item.key)
        state.mark_checked(feed.id)
        state.save()
        return FeedCheckResult(
            feed_id=feed.id,
            fetched=len(items),
            sent=0,
            skipped_existing=len(items),
            initialized_without_send=True,
        )

    unseen = [item for item in items if not state.has_seen(feed.id, item.key)]
    to_send = unseen[-config.max_items_per_check :]

    sent = 0
    for item in to_send:
        if not dry_run:
            await sender.send_item(feed, item)
            state.mark_seen(feed.id, item.key)
            state.mark_checked(feed.id)
            state.save()
        else:
            await sender.send_item(feed, item)
            sent += 1
            continue
        sent += 1

    if dry_run:
        state.mark_checked(feed.id)
    else:
        for item in unseen[: max(0, len(unseen) - len(to_send))]:
            state.mark_seen(feed.id, item.key)
        state.mark_checked(feed.id)
        state.save()

    return FeedCheckResult(
        feed_id=feed.id,
        fetched=len(items),
        sent=sent,
        skipped_existing=len(items) - len(unseen),
    )


async def run_forever(
    config: AppConfig,
    dry_run: bool = False,
    fetcher: FetchFeed = fetch_feed,
) -> None:
    next_due = {feed.id: 0.0 for feed in config.enabled_feeds()}
    sender: Sender = DryRunSender() if dry_run else BoChatSender(config)
    state = RssState.load(config.state_path)
    try:
        while True:
            now = time.monotonic()
            for feed in config.enabled_feeds():
                if now < next_due.get(feed.id, 0.0):
                    continue
                try:
                    result = await check_feed(
                        config=config,
                        feed_id=feed.id,
                        dry_run=dry_run,
                        fetcher=fetcher,
                        sender=sender,
                        state=state,
                    )
                    print(
                        f"[{feed.id}] fetched={result.fetched} sent={result.sent} "
                        f"skipped={result.skipped_existing}"
                    )
                except Exception as exc:
                    print(f"[{feed.id}] check failed: {exc}")
                interval = feed.interval_secs or config.default_interval_secs
                next_due[feed.id] = time.monotonic() + interval
            await asyncio.sleep(5)
    except KeyboardInterrupt:
        print("收到退出信号，停止 RSS 订阅器")
    finally:
        await sender.close()


def find_feed(config: AppConfig, feed_id: str) -> FeedConfig:
    for feed in config.feeds:
        if feed.id == feed_id:
            return feed
    raise ValueError(f"未找到 feed: {feed_id}")
