# tests/test_tools.py
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from src.tools import execute_exa_search_news, execute_exa_search_tweets, execute_exa_get_contents, execute_fetch_reddit_rss


def _make_exa_result(title="Test Article", url="https://example.com/1", highlights=None):
    result = MagicMock()
    result.title = title
    result.url = url
    result.highlights = highlights or ["This is a highlight"]
    result.published_date = "2026-03-20T10:00:00Z"
    return result


def test_exa_search_news_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="AI News", url="https://news.com/1")]
    mock_exa.search_and_contents.return_value = mock_response

    result = execute_exa_search_news(mock_exa, "AI news", num_results=5)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "AI News"
    assert parsed[0]["url"] == "https://news.com/1"


def test_exa_search_news_returns_error_on_failure():
    mock_exa = MagicMock()
    mock_exa.search_and_contents.side_effect = Exception("API Error")
    result = execute_exa_search_news(mock_exa, "AI news", num_results=5)
    parsed = json.loads(result)
    assert "error" in parsed


def test_exa_search_tweets_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="AI Tweet", url="https://x.com/1")]
    mock_exa.search_and_contents.return_value = mock_response
    result = execute_exa_search_tweets(mock_exa, "Claude AI", num_results=5)
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "AI Tweet"


def test_exa_get_contents_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="Full Article", url="https://example.com/full")]
    mock_exa.get_contents.return_value = mock_response
    result = execute_exa_get_contents(mock_exa, ["https://example.com/full"])
    parsed = json.loads(result)
    assert len(parsed) == 1
    assert parsed[0]["title"] == "Full Article"


def test_exa_get_contents_returns_error_on_failure():
    mock_exa = MagicMock()
    mock_exa.get_contents.side_effect = Exception("Timeout")
    result = execute_exa_get_contents(mock_exa, ["https://example.com/1"])
    parsed = json.loads(result)
    assert "error" in parsed


def test_fetch_reddit_rss_returns_formatted_results():
    from src.models import create_article
    mock_articles = [
        create_article(
            url="https://reddit.com/r/ML/1", title="ML Post",
            content="Content", source="reddit", source_name="MachineLearning",
            published_at=datetime.now(timezone.utc),
        )
    ]
    with patch("src.tools.asyncio") as mock_asyncio:
        mock_asyncio.run.return_value = mock_articles
        result = execute_fetch_reddit_rss(["MachineLearning"], "test/1.0")
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["title"] == "ML Post"


def test_fetch_reddit_rss_returns_error_on_failure():
    with patch("src.tools.asyncio") as mock_asyncio:
        mock_asyncio.run.side_effect = Exception("Network error")
        result = execute_fetch_reddit_rss(["MachineLearning"], "test/1.0")
        parsed = json.loads(result)
        assert "error" in parsed
