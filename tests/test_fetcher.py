# tests/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.fetcher import fetch_reddit_rss

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
