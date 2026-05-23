"""Supplementary unit tests for bochat-rss-subscriber.

Covers gaps identified in the test plan:
- config edge cases
- rss parsing edge cases
- sender formatting edge cases
- state edge cases
- runner edge cases
"""

from pathlib import Path
import asyncio

import pytest

from bochat_rss.config import ConfigError, parse_config, AppConfig, FeedConfig
from bochat_rss.rss import (
    RssItem,
    make_item_key,
    parse_feed_content,
    sort_items_old_to_new,
)
from bochat_rss.runner import (
    FeedCheckResult,
    check_all,
    check_feed_by_id,
    check_feed,
    find_feed,
    latest_items,
)
from bochat_rss.sender import (
    BoChatSender,
    DryRunSender,
    format_item_message,
    _compact_summary,
    _format_published_at,
    _strip_html,
)
from bochat_rss.state import RssState, StateError


# ── helpers ──────────────────────────────────────────────────────────────────

def base_config_dict(tmp_path: Path):
    return {
        "base_url": "http://127.0.0.1:8080",
        "bot_token": "b_token",
        "state_path": "rss_state.json",
        "feeds": [
            {
                "id": "rust",
                "name": "Rust",
                "url": "https://example.com/feed.xml",
                "group_id": "g_1",
            }
        ],
    }


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


def rss_items(count: int, *, prefix: str = "key") -> list[RssItem]:
    return [
        RssItem(
            feed_id="feed",
            source_name="Feed",
            key=f"{prefix}-{i}",
            title=f"Title {i}",
            link=f"https://example.com/{i}",
            summary=None,
            published_at=f"2026-04-25T10:0{i}:00+00:00",
        )
        for i in range(count)
    ]


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


# ── config ───────────────────────────────────────────────────────────────────

def test_feed_interval_secs_custom_value(tmp_path: Path):
    raw = base_config_dict(tmp_path)
    raw["feeds"][0]["interval_secs"] = 600
    cfg = parse_config(raw, base_dir=tmp_path)
    assert cfg.feeds[0].interval_secs == 600


def test_disabled_feed_excluded_from_enabled(tmp_path: Path):
    raw = base_config_dict(tmp_path)
    raw["feeds"].append({
        "id": "disabled-feed",
        "url": "https://example.com/rss.xml",
        "group_id": "g_2",
        "enabled": False,
    })
    cfg = parse_config(raw, base_dir=tmp_path)
    assert len(cfg.feeds) == 2
    assert len(cfg.enabled_feeds()) == 1


def test_base_url_without_http_scheme_rejected(tmp_path: Path):
    raw = base_config_dict(tmp_path)
    raw["base_url"] = "ftp://127.0.0.1:8080"
    with pytest.raises(ConfigError, match="http:// 或 https://"):
        parse_config(raw, base_dir=tmp_path)


# ── rss ──────────────────────────────────────────────────────────────────────

def test_make_item_key_fallback_to_title_and_date():
    entry = {"title": "Hello", "published": "2026-01-01T00:00:00Z"}
    key = make_item_key(entry)
    assert isinstance(key, str) and len(key) == 64


def test_sort_items_old_to_new():
    items = [
        RssItem("f", "F", "k3", "T3", None, None, "2026-04-25T10:03:00+00:00"),
        RssItem("f", "F", "k1", "T1", None, None, "2026-04-25T10:01:00+00:00"),
        RssItem("f", "F", "k2", "T2", None, None, "2026-04-25T10:02:00+00:00"),
    ]
    sorted_items = sort_items_old_to_new(items)
    assert [i.key for i in sorted_items] == ["k1", "k2", "k3"]


ATOM = """<?xml version="1.0" encoding="UTF-8" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Example</title>
  <entry>
    <id>atom-1</id>
    <title>Atom Entry</title>
    <link href="https://example.com/atom-1"/>
    <summary>Atom summary content</summary>
  </entry>
</feed>
"""


def test_parse_atom_feed():
    feed = FeedConfig(id="atom", name="Atom", url="https://example.com/atom.xml", group_id="g_1")
    items = parse_feed_content(ATOM, feed)
    assert len(items) == 1
    assert items[0].title == "Atom Entry"
    assert items[0].key == make_item_key({"id": "atom-1"})


def test_fetch_feed_file_protocol(tmp_path: Path):
    feed_xml = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><title>Local</title>
<item><guid>local-1</guid><title>Local Item</title></item>
</channel></rss>"""
    local_file = tmp_path / "test_feed.xml"
    local_file.write_text(feed_xml, encoding="utf-8")

    from bochat_rss.rss import fetch_feed
    feed = FeedConfig(id="local", name="Local", url=f"file://{local_file}", group_id="g_1")
    items = fetch_feed(feed)
    assert len(items) == 1
    assert items[0].title == "Local Item"


# ── sender ───────────────────────────────────────────────────────────────────

def test_strip_html_empty_and_plain_text():
    assert _strip_html("") == ""
    assert _strip_html("Plain text") == "Plain text"


def test_strip_html_nested_tags():
    html = "<div><p>Nested <strong>bold</strong> and <em>italic</em>.</p></div>"
    text = _strip_html(html)
    assert "Nested" in text
    assert "bold" in text
    assert "italic" in text


def test_compact_summary_under_max_len():
    assert _compact_summary("Short summary", max_len=500) == "Short summary"


def test_compact_summary_truncation():
    result = _compact_summary("a" * 600, max_len=100)
    assert len(result) <= 100
    assert result.endswith("...")


def test_format_published_at_utc_z_suffix():
    assert "UTC" in _format_published_at("2026-04-25T10:00:00Z")


def test_format_published_at_with_offset():
    formatted = _format_published_at("2026-04-25T10:00:00+08:00")
    assert "UTC+08:00" in formatted


def test_dry_run_sender_accumulates_messages():
    sender = DryRunSender()
    feed = FeedConfig(id="f", name="F", url="https://x.com/rss", group_id="g_1")
    item = RssItem("f", "F", "k1", "Hello", "https://x.com/1", None, "2026-04-25T10:00:00+00:00")
    import asyncio
    asyncio.run(sender.send_item(feed, item))
    assert len(sender.messages) == 1
    assert sender.messages[0] == ("g_1", format_item_message(item))


# ── state ────────────────────────────────────────────────────────────────────

def test_state_mark_seen_truncates_when_exceeds_max(tmp_path: Path):
    state = RssState.load(tmp_path / "state.json")
    for i in range(1500):
        state.mark_seen("feed", f"key-{i}", max_seen=500)
    state.save()

    loaded = RssState.load(tmp_path / "state.json")
    feed_state = loaded.feeds.get("feed")
    assert feed_state is not None
    assert len(feed_state.seen) <= 500


def test_state_handles_corrupted_json(tmp_path: Path):
    path = tmp_path / "corrupt.json"
    path.write_text("this is not json", encoding="utf-8")
    with pytest.raises(StateError):
        RssState.load(path)


def test_state_atomic_write_does_not_lose_data(tmp_path: Path):
    path = tmp_path / "atomic.json"
    state = RssState.load(path)
    state.mark_seen("feed", "key-1")
    state.mark_checked("feed")
    state.save()

    loaded = RssState.load(path)
    assert loaded.has_seen("feed", "key-1")
    assert loaded.feeds["feed"].last_checked_at is not None


# ── runner ───────────────────────────────────────────────────────────────────

def test_send_existing_on_first_run_true(tmp_path: Path):
    cfg = make_config(tmp_path, send_existing=True)
    sender = FakeSender()
    state = RssState.load(cfg.state_path)

    def fetcher(feed):
        return rss_items(3)

    result = asyncio.run(
        check_feed(cfg, "feed", dry_run=False, fetcher=fetcher, sender=sender, state=state)
    )
    assert result.sent == 3
    assert len(sender.sent) == 3


def test_check_all_with_multiple_feeds(tmp_path: Path):
    cfg = AppConfig(
        base_url="http://127.0.0.1:8080",
        bot_token="b_token",
        state_path=tmp_path / "multi_state.json",
        default_interval_secs=300,
        send_existing_on_first_run=True,
        max_items_per_check=10,
        feeds=[
            FeedConfig(id="f1", name="F1", url="https://x.com/1.xml", group_id="g_1"),
            FeedConfig(id="f2", name="F2", url="https://x.com/2.xml", group_id="g_1"),
        ],
    )
    sender = FakeSender()

    def fetcher(feed):
        if feed.id == "f1":
            return rss_items(2, prefix="f1")
        return rss_items(3, prefix="f2")

    results = asyncio.run(check_all(cfg, fetcher=fetcher, sender=sender))
    assert len(results) == 2
    assert results[0].sent + results[1].sent == 5


def test_find_feed_raises_for_unknown_id(tmp_path: Path):
    cfg = make_config(tmp_path)
    with pytest.raises(ValueError, match="未找到 feed"):
        find_feed(cfg, "nonexistent")


def test_latest_items_respects_limit(tmp_path: Path):
    cfg = make_config(tmp_path)

    def fetcher(feed):
        return rss_items(10)

    items = asyncio.run(latest_items(cfg, "feed", limit=3, fetcher=fetcher))
    assert len(items) == 3


def test_runner_preserves_existing_state_on_error(tmp_path: Path):
    """When a send fails, seen keys should NOT be marked."""
    cfg = make_config(tmp_path, send_existing=True)
    state = RssState.load(cfg.state_path)

    def fetcher(feed):
        return rss_items(2)

    sender = FakeSender(fail=True)
    with pytest.raises(RuntimeError):
        asyncio.run(
            check_feed(cfg, "feed", dry_run=False, fetcher=fetcher, sender=sender, state=state)
        )
    # after failure, nothing should be marked
    assert not state.has_seen("feed", "key-0")
    assert not state.has_seen("feed", "key-1")
