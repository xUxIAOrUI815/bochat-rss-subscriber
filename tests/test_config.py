from pathlib import Path

import pytest

from bochat_rss.config import ConfigError, parse_config


def valid_config(tmp_path: Path):
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


def test_parse_config_defaults(tmp_path: Path):
    cfg = parse_config(valid_config(tmp_path), base_dir=tmp_path)

    assert cfg.base_url == "http://127.0.0.1:8080"
    assert cfg.state_path == tmp_path / "rss_state.json"
    assert cfg.default_interval_secs == 300
    assert cfg.max_items_per_check == 5
    assert cfg.send_existing_on_first_run is False
    assert cfg.feeds[0].enabled is True


def test_duplicate_feed_id_rejected(tmp_path: Path):
    raw = valid_config(tmp_path)
    raw["feeds"].append(dict(raw["feeds"][0]))

    with pytest.raises(ConfigError, match="feed id 重复"):
        parse_config(raw, base_dir=tmp_path)


def test_missing_required_field_rejected(tmp_path: Path):
    raw = valid_config(tmp_path)
    del raw["bot_token"]

    with pytest.raises(ConfigError, match="bot_token"):
        parse_config(raw, base_dir=tmp_path)
