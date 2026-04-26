from bochat_rss.config import FeedConfig
from bochat_rss.rss import parse_feed_content


RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Example</title>
  <item>
    <guid>item-1</guid>
    <title>First</title>
    <link>https://example.com/first</link>
    <pubDate>Sat, 25 Apr 2026 10:00:00 GMT</pubDate>
    <description>Hello world</description>
  </item>
</channel>
</rss>
"""


def test_parse_feed_content_and_stable_key():
    feed = FeedConfig(
        id="example",
        name="Example",
        url="https://example.com/rss.xml",
        group_id="g_1",
    )

    first = parse_feed_content(RSS, feed)
    second = parse_feed_content(RSS, feed)

    assert len(first) == 1
    assert first[0].title == "First"
    assert first[0].summary == "Hello world"
    assert first[0].key == second[0].key
