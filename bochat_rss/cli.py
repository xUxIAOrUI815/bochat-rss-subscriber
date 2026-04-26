from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from .config import ConfigError, load_config
from .runner import check_all, check_feed_by_id, latest_items, run_forever
from .sender import format_item_message

app = typer.Typer(help="BoChat RSS/Atom subscriber bot")


@app.command("init-config")
def init_config(path: Path) -> None:
    """Generate an example config file."""
    if path.exists():
        raise typer.BadParameter(f"文件已存在: {path}")
    example = Path(__file__).resolve().parents[1] / "examples" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    typer.echo(f"已生成配置文件: {path}")


@app.command("list")
def list_feeds(config: Path = typer.Option(..., "--config", "-c")) -> None:
    cfg = _load_or_exit(config)
    for feed in cfg.feeds:
        interval = feed.interval_secs or cfg.default_interval_secs
        status = "enabled" if feed.enabled else "disabled"
        typer.echo(
            f"{feed.id}\t{status}\tinterval={interval}s\tgroup={feed.group_id}\t{feed.name}"
        )


@app.command("latest")
def latest(
    feed_id: str,
    config: Path = typer.Option(..., "--config", "-c"),
    limit: int = typer.Option(5, "--limit", "-n", min=1),
) -> None:
    cfg = _load_or_exit(config)
    items = asyncio.run(latest_items(cfg, feed_id, limit))
    for item in items:
        typer.echo(format_item_message(item))
        typer.echo("")


@app.command("check")
def check(
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    results = asyncio.run(check_all(cfg, dry_run=dry_run))
    for result in results:
        typer.echo(
            f"{result.feed_id}: fetched={result.fetched}, sent={result.sent}, "
            f"skipped={result.skipped_existing}"
        )


@app.command("check-feed")
def check_feed(
    feed_id: str,
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    result = asyncio.run(check_feed_by_id(cfg, feed_id, dry_run=dry_run))
    typer.echo(
        f"{result.feed_id}: fetched={result.fetched}, sent={result.sent}, "
        f"skipped={result.skipped_existing}"
    )


@app.command("run")
def run(
    config: Path = typer.Option(..., "--config", "-c"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    cfg = _load_or_exit(config)
    asyncio.run(run_forever(cfg, dry_run=dry_run))


def _load_or_exit(path: Path):
    try:
        return load_config(path)
    except ConfigError as exc:
        typer.echo(f"配置错误: {exc}", err=True)
        raise typer.Exit(code=2) from exc
