from pathlib import Path
import asyncio

import pytest

from bochat_rss.config import AppConfig, FeedConfig
from bochat_rss.rss import RssItem
from bochat_rss.runner import check_feed_by_id, latest_items
from bochat_rss.state import RssState


class FakeSender:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.sent: list[RssItem] = []

    async def send_item(self, feed, item):
        if self.fail:
            raise RuntimeError("send failed")
        self.sent.append(item)

    async def close(self):
        return None


def make_config(tmp_path: Path, send_existing: bool = False, max_items: int = 5) -> AppConfig:
    return AppConfig(
        base_url="http://127.0.0.1:8080",
        bot_token="b_token",
        state_path=tmp_path / "state.json",
        default_interval_secs=300,
        send_existing_on_first_run=send_existing,
        max_items_per_check=max_items,
        feeds=[
            FeedConfig(
                id="feed",
                name="Feed",
                url="https://example.com/rss.xml",
                group_id="g_1",
            )
        ],
    )


def items(count: int):
    return [
        RssItem(
            feed_id="feed",
            source_name="Feed",
            key=f"key-{index}",
            title=f"Title {index}",
            link=f"https://example.com/{index}",
            summary=None,
            published_at=f"2026-04-25T10:0{index}:00+00:00",
        )
        for index in range(count)
    ]


def fetcher(feed):
    return items(3)


def test_first_run_marks_seen_without_sending(tmp_path: Path):
    cfg = make_config(tmp_path)
    sender = FakeSender()

    result = asyncio.run(check_feed_by_id(cfg, "feed", fetcher=fetcher, sender=sender))

    assert result.initialized_without_send is True
    assert result.sent == 0
    assert len(sender.sent) == 0
    state = RssState.load(cfg.state_path)
    assert state.has_seen("feed", "key-0")
    assert state.has_seen("feed", "key-2")


def test_max_items_per_check_limits_send_count(tmp_path: Path):
    cfg = make_config(tmp_path, send_existing=True, max_items=2)
    sender = FakeSender()

    result = asyncio.run(check_feed_by_id(cfg, "feed", fetcher=fetcher, sender=sender))

    assert result.sent == 2
    assert [item.key for item in sender.sent] == ["key-1", "key-2"]


def test_dry_run_does_not_mark_seen(tmp_path: Path):
    cfg = make_config(tmp_path, send_existing=True)
    sender = FakeSender()

    result = asyncio.run(
        check_feed_by_id(
            cfg,
            "feed",
            dry_run=True,
            fetcher=fetcher,
            sender=sender,
        )
    )

    assert result.sent == 3
    assert len(sender.sent) == 3
    state = RssState.load(cfg.state_path)
    assert not state.has_seen("feed", "key-0")


def test_send_failure_does_not_mark_seen(tmp_path: Path):
    cfg = make_config(tmp_path, send_existing=True)
    sender = FakeSender(fail=True)

    with pytest.raises(RuntimeError, match="send failed"):
        asyncio.run(check_feed_by_id(cfg, "feed", fetcher=fetcher, sender=sender))

    state = RssState.load(cfg.state_path)
    assert not state.has_seen("feed", "key-0")


def test_latest_returns_items_without_sending(tmp_path: Path):
    cfg = make_config(tmp_path)

    latest = asyncio.run(latest_items(cfg, "feed", limit=2, fetcher=fetcher))

    assert [item.key for item in latest] == ["key-1", "key-2"]
