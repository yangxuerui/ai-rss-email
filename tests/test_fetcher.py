# tests/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.fetcher import fetch_twitter_rss, fetch_reddit_rss, fetch_all

TWITTER_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>@openai</title>
  <item>
    <title>New GPT release</title>
    <link>https://twitter.com/openai/status/123</link>
    <description>We are releasing GPT-5 today</description>
    <pubDate>Thu, 20 Mar 2026 10:00:00 +0000</pubDate>
  </item>
</channel>
</rss>"""

REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>New paper on transformers</title>
    <link href="https://reddit.com/r/MachineLearning/comments/abc"/>
    <content>Interesting paper about transformers</content>
    <updated>2026-03-20T10:00:00+00:00</updated>
  </entry>
</feed>"""


class AsyncContextManager:
    """Helper to mock async context manager for aiohttp responses."""
    def __init__(self, return_value):
        self.return_value = return_value
    async def __aenter__(self):
        return self.return_value
    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_fetch_twitter_rss_parses_articles():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=TWITTER_RSS)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://rsshub.app"],
        account="openai",
    )
    assert len(articles) == 1
    assert articles[0].source == "twitter"
    assert articles[0].source_name == "openai"
    assert "GPT" in articles[0].title


@pytest.mark.asyncio
async def test_fetch_twitter_rss_fallback_on_failure():
    fail_response = AsyncMock()
    fail_response.status = 500

    ok_response = AsyncMock()
    ok_response.status = 200
    ok_response.text = AsyncMock(return_value=TWITTER_RSS)

    mock_session = AsyncMock()
    responses = [AsyncContextManager(fail_response), AsyncContextManager(ok_response)]
    mock_session.get = MagicMock(side_effect=responses)

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://bad.instance", "https://rsshub.app"],
        account="openai",
    )
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_fetch_reddit_rss_parses_articles():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=REDDIT_RSS)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_reddit_rss(
        session=mock_session,
        subreddit="MachineLearning",
        user_agent="test/1.0",
    )
    assert len(articles) == 1
    assert articles[0].source == "reddit"
    assert articles[0].source_name == "MachineLearning"


@pytest.mark.asyncio
async def test_fetch_twitter_rss_returns_empty_on_malformed_xml():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<not valid xml at all")

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://rsshub.app"],
        account="openai",
    )
    assert articles == []


@pytest.mark.asyncio
async def test_fetch_reddit_rss_returns_empty_on_empty_feed():
    empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=empty_rss)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_reddit_rss(
        session=mock_session,
        subreddit="MachineLearning",
        user_agent="test/1.0",
    )
    assert articles == []
