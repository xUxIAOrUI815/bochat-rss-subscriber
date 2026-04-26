from pathlib import Path

from bochat_rss.state import RssState


def test_state_read_write_seen(tmp_path: Path):
    path = tmp_path / "state.json"
    state = RssState.load(path)

    assert not state.is_feed_initialized("feed")
    assert not state.has_seen("feed", "key")

    state.mark_seen("feed", "key")
    state.mark_checked("feed")
    state.save()

    loaded = RssState.load(path)
    assert loaded.is_feed_initialized("feed")
    assert loaded.has_seen("feed", "key")
    assert loaded.feeds["feed"].last_checked_at is not None
