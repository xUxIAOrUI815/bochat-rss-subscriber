"""Integration tests for bochat-rss-subscriber against live BoChat server.

Requires a running BoChat instance with a test bot already in the target group.

Environment:
  BOCHAT_BASE_URL, BOCHAT_BOT_TOKEN, BOCHAT_GROUP_ID
  (set via environment variables)
"""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from bochat_rss.config import AppConfig, FeedConfig
from bochat_rss.rss import fetch_feed, parse_feed_content, RssItem
from bochat_rss.runner import check_all, check_feed_by_id, latest_items
from bochat_rss.sender import BoChatSender, DryRunSender
from bochat_rss.state import RssState

# ── Test environment constants ───────────────────────────────────────────────
# These must be set via environment variables before running integration tests:
#   BOCHAT_BASE_URL, BOCHAT_BOT_TOKEN, BOCHAT_GROUP_ID

BASE_URL = os.environ.get("BOCHAT_BASE_URL", "http://127.0.0.1:8080")
BOT_TOKEN = os.environ.get("BOCHAT_BOT_TOKEN", "")
GROUP_ID = os.environ.get("BOCHAT_GROUP_ID", "")

# Public RSS feeds for testing
RUST_BLOG_FEED = "https://blog.rust-lang.org/feed.xml"
GITHUB_BLOG_FEED = "https://github.blog/feed/"


def make_integration_config(tmp_path: Path, feeds: list[FeedConfig] | None = None) -> AppConfig:
    return AppConfig(
        base_url=BASE_URL,
        bot_token=BOT_TOKEN,
        state_path=tmp_path / "integration_state.json",
        default_interval_secs=300,
        send_existing_on_first_run=False,
        max_items_per_check=3,
        feeds=feeds or [
            FeedConfig(
                id="rust-blog",
                name="Rust Blog",
                url=RUST_BLOG_FEED,
                group_id=GROUP_ID,
            )
        ],
    )


# ── Real RSS feed fetching ───────────────────────────────────────────────────

def test_fetch_real_public_rss_feed():
    """Verify we can fetch and parse a real public RSS feed."""
    feed = FeedConfig(
        id="rust-blog",
        name="Rust Blog",
        url=RUST_BLOG_FEED,
        group_id=GROUP_ID,
    )
    items = fetch_feed(feed, timeout_secs=30)
    assert len(items) > 0, "Should get at least one item from Rust Blog feed"
    for item in items:
        assert item.feed_id == "rust-blog"
        assert item.title
        assert item.key
        # keys are SHA256 hex = 64 chars
        assert len(item.key) == 64


def test_fetch_real_atom_feed():
    """Verify we can fetch and parse a real Atom feed (GitHub Blog)."""
    feed = FeedConfig(
        id="github-blog",
        name="GitHub Blog",
        url=GITHUB_BLOG_FEED,
        group_id=GROUP_ID,
    )
    items = fetch_feed(feed, timeout_secs=30)
    assert len(items) > 0, "Should get at least one item from GitHub Blog feed"


# ── BoChat sender integration ────────────────────────────────────────────────

def test_real_sender_send_text_to_group():
    """Send a real message to the BoChat group and verify msg_id returned."""
    async def _test():
        cfg = make_integration_config(Path("/tmp"))
        sender = BoChatSender(cfg)
        try:
            feed = FeedConfig(id="test", name="Test", url=RUST_BLOG_FEED, group_id=GROUP_ID)
            item = RssItem(
                feed_id="test",
                source_name="Integration Test",
                key="manual-test-001",
                title="Integration Test Message",
                link="https://example.com/test",
                summary="This is an automated integration test.",
                published_at="2026-05-22T13:00:00+00:00",
            )
            result = await sender.send_item(feed, item)
            assert result.msg_id is not None
            assert result.dry_run is False
        finally:
            await sender.close()

    asyncio.run(_test())


def test_dry_run_sender_no_api_call():
    """Dry-run sender should accumulate messages without calling BoChat API."""
    sender = DryRunSender()
    feed = FeedConfig(id="f", name="F", url="https://x.com/rss", group_id=GROUP_ID)
    item = RssItem("f", "F", "k1", "DR Dry Run", "https://x.com/1", None, "2026-05-22T13:00:00+00:00")

    async def _test():
        result = await sender.send_item(feed, item)
        assert result.dry_run is True
        assert result.msg_id is None
        assert len(sender.messages) == 1

    asyncio.run(_test())


# ── Runner integration (dry-run first, then real) ────────────────────────────

def test_check_feed_dry_run_with_real_feed(tmp_path: Path):
    """Run check on a real feed in dry-run mode - should not mark state."""
    cfg = make_integration_config(tmp_path)
    result: list = asyncio.run(check_all(cfg, dry_run=True))
    assert len(result) >= 1
    for r in result:
        assert r.fetched > 0
        # dry_run should report sent but not persist
        assert r.sent >= 0
    # Note: first run with send_existing_on_first_run=False marks all existing
    # feed items as "seen" even in dry_run mode (to avoid sending history).
    # This is expected behavior to prevent accidental spam on first run.


def test_check_feed_real_send_to_group(tmp_path: Path):
    """Run check on a real feed with real sending - should send and persist."""
    cfg = make_integration_config(tmp_path)
    result: list = asyncio.run(check_all(cfg, dry_run=False))
    assert len(result) >= 1
    for r in result:
        assert r.fetched > 0
        # First run without send_existing marks all as seen
        assert r.skipped_existing >= 0

    # State should be persistent
    state = RssState.load(cfg.state_path)
    assert state.is_feed_initialized("rust-blog")


def test_latest_items_with_real_feed(tmp_path: Path):
    """Verify latest_items command works with a real feed."""
    cfg = make_integration_config(tmp_path)
    items: list = asyncio.run(latest_items(cfg, "rust-blog", limit=3))
    assert 1 <= len(items) <= 3
    for item in items:
        assert item.title
        assert item.key


def test_check_single_feed_with_real_data(tmp_path: Path):
    """Check a single feed by ID against the real server."""
    cfg = make_integration_config(tmp_path)
    result = asyncio.run(check_feed_by_id(cfg, "rust-blog", dry_run=True))
    assert result.feed_id == "rust-blog"
    assert result.fetched > 0


# ── Multi-feed integration ───────────────────────────────────────────────────

def test_multi_feed_check_all_dry_run(tmp_path: Path):
    """Test check_all with multiple real feeds in dry-run mode."""
    cfg = AppConfig(
        base_url=BASE_URL,
        bot_token=BOT_TOKEN,
        state_path=tmp_path / "multi_state.json",
        default_interval_secs=300,
        send_existing_on_first_run=False,
        max_items_per_check=2,
        feeds=[
            FeedConfig(id="rust-blog", name="Rust Blog", url=RUST_BLOG_FEED, group_id=GROUP_ID),
            FeedConfig(id="github-blog", name="GitHub Blog", url=GITHUB_BLOG_FEED, group_id=GROUP_ID),
        ],
    )
    results = asyncio.run(check_all(cfg, dry_run=True))
    assert len(results) == 2
    for r in results:
        assert r.fetched > 0, f"Feed {r.feed_id} should fetch items"


# ── Error handling integration ───────────────────────────────────────────────

def test_invalid_bot_token_graceful_error(tmp_path: Path):
    """Using an invalid bot token should result in a clear error."""
    cfg = AppConfig(
        base_url=BASE_URL,
        bot_token="b_fake:0:badtoken",
        state_path=tmp_path / "state.json",
        default_interval_secs=300,
        send_existing_on_first_run=True,
        max_items_per_check=1,
        feeds=[
            FeedConfig(id="test", name="Test", url=RUST_BLOG_FEED, group_id=GROUP_ID),
        ],
    )
    with pytest.raises(Exception):
        asyncio.run(check_all(cfg, dry_run=False))


def test_fetch_network_error_handled():
    """Fetching a non-existent URL should raise RssError."""
    from bochat_rss.rss import RssError, fetch_feed
    feed = FeedConfig(id="bad", name="Bad", url="https://does-not-exist.invalid/feed.xml", group_id=GROUP_ID)
    with pytest.raises(RssError):
        fetch_feed(feed, timeout_secs=5)
