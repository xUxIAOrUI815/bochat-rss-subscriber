from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import tomllib


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class FeedConfig:
    id: str
    name: str
    url: str
    group_id: str
    enabled: bool = True
    interval_secs: int | None = None


@dataclass(frozen=True)
class AppConfig:
    base_url: str
    bot_token: str
    state_path: Path
    default_interval_secs: int
    send_existing_on_first_run: bool
    max_items_per_check: int
    feeds: list[FeedConfig]

    def enabled_feeds(self) -> list[FeedConfig]:
        return [feed for feed in self.feeds if feed.enabled]


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    try:
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"配置文件不存在: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"配置文件 TOML 格式错误: {exc}") from exc

    return parse_config(raw, base_dir=config_path.parent)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> AppConfig:
    base_dir = base_dir or Path.cwd()
    base_url = _required_str(raw, "base_url")
    bot_token = _required_str(raw, "bot_token")
    state_path_raw = _str_value(raw.get("state_path", "./rss_state.json"), "state_path")
    default_interval_secs = _positive_int(
        raw.get("default_interval_secs", 300), "default_interval_secs"
    )
    max_items_per_check = _positive_int(
        raw.get("max_items_per_check", 5), "max_items_per_check"
    )
    send_existing_on_first_run = bool(raw.get("send_existing_on_first_run", False))

    if not _has_http_scheme(base_url):
        raise ConfigError("base_url 必须是 http:// 或 https:// 地址")

    state_path = Path(state_path_raw)
    if not state_path.is_absolute():
        state_path = base_dir / state_path

    feeds_raw = raw.get("feeds")
    if not isinstance(feeds_raw, list) or not feeds_raw:
        raise ConfigError("至少需要配置一个 [[feeds]]")

    feeds: list[FeedConfig] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(feeds_raw):
        if not isinstance(item, dict):
            raise ConfigError(f"feeds[{index}] 必须是对象")
        feed = _parse_feed(item, index)
        if feed.id in seen_ids:
            raise ConfigError(f"feed id 重复: {feed.id}")
        seen_ids.add(feed.id)
        feeds.append(feed)

    return AppConfig(
        base_url=base_url.rstrip("/"),
        bot_token=bot_token,
        state_path=state_path,
        default_interval_secs=default_interval_secs,
        send_existing_on_first_run=send_existing_on_first_run,
        max_items_per_check=max_items_per_check,
        feeds=feeds,
    )


def _parse_feed(raw: dict[str, Any], index: int) -> FeedConfig:
    feed_id = _required_str(raw, "id", prefix=f"feeds[{index}]")
    name = _str_value(raw.get("name", feed_id), f"feeds[{index}].name")
    url = _required_str(raw, "url", prefix=f"feeds[{index}]")
    group_id = _required_str(raw, "group_id", prefix=f"feeds[{index}]")
    enabled = bool(raw.get("enabled", True))
    interval_secs = raw.get("interval_secs")
    if interval_secs is not None:
        interval_secs = _positive_int(interval_secs, f"feeds[{index}].interval_secs")

    if not _has_http_scheme(url):
        raise ConfigError(f"feeds[{index}].url 必须是 http:// 或 https:// 地址")

    return FeedConfig(
        id=feed_id,
        name=name,
        url=url,
        group_id=group_id,
        enabled=enabled,
        interval_secs=interval_secs,
    )


def _required_str(raw: dict[str, Any], key: str, prefix: str | None = None) -> str:
    label = f"{prefix}.{key}" if prefix else key
    if key not in raw:
        raise ConfigError(f"缺少必填配置: {label}")
    return _str_value(raw[key], label)


def _str_value(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{label} 必须是非空字符串")
    return value.strip()


def _positive_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ConfigError(f"{label} 必须是正整数")
    return value


def _has_http_scheme(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
