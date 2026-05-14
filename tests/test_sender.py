from bochat_rss.rss import RssItem
from bochat_rss.sender import format_item_message


def test_format_item_message_uses_markdown_human_date_and_plain_summary():
    item = RssItem(
        feed_id="feed",
        source_name="Feed",
        key="key",
        title="Title",
        link="https://example.com/post",
        summary="<p>Hello <strong>world</strong>&nbsp;!</p><p>Second line.</p>",
        published_at="2026-04-25T10:00:00+00:00",
    )

    assert format_item_message(item) == (
        "### [Title](https://example.com/post)\n"
        "**来源**：Feed\n"
        "**发布时间**：2026-04-25 10:00 UTC\n"
        "\n"
        "Hello world ! Second line."
    )


def test_format_item_message_keeps_unparseable_date():
    item = RssItem(
        feed_id="feed",
        source_name="Feed",
        key="key",
        title="Title",
        link=None,
        summary=None,
        published_at="not a date",
    )

    assert format_item_message(item) == (
        "### Title\n"
        "**来源**：Feed\n"
        "**发布时间**：not a date"
    )
