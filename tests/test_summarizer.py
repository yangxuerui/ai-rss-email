# tests/test_summarizer.py
from datetime import datetime, timezone
from unittest.mock import MagicMock
from src.summarizer import summarize_articles, _build_prompt, _truncate_content, _batch_articles
from src.models import create_article


def make_articles(count=3):
    return [
        create_article(
            url=f"https://example.com/{i}",
            title=f"Article {i}",
            content=f"Content for article {i} about AI developments",
            source="twitter",
            source_name="openai",
            published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
        )
        for i in range(count)
    ]


def test_build_prompt_includes_articles():
    articles = make_articles(2)
    prompt = _build_prompt(articles)
    assert "Article 0" in prompt
    assert "Article 1" in prompt
    assert "https://example.com/0" in prompt


def test_truncate_content():
    long_text = "x" * 1000
    truncated = _truncate_content(long_text, max_chars=500)
    assert len(truncated) <= 503  # 500 + "..."
    assert truncated.endswith("...")

    short_text = "short"
    assert _truncate_content(short_text, max_chars=500) == "short"


def test_summarize_articles_calls_claude():
    articles = make_articles(2)

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="# 今日概述\n\nAI领域发生了重大变化。")]
    mock_message.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    result = summarize_articles(articles, mock_client, "claude-sonnet-4-latest", 4096)

    assert "今日概述" in result
    mock_client.messages.create.assert_called_once()


def test_summarize_articles_fallback_on_error():
    articles = make_articles(2)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")

    result = summarize_articles(articles, mock_client, "claude-sonnet-4-latest", 4096)

    # Fallback: raw article list
    assert "Article 0" in result
    assert "Article 1" in result


def test_batch_articles_splits_by_char_limit():
    articles = make_articles(10)
    batches = _batch_articles(articles, max_chars_per_batch=200)
    assert len(batches) > 1
    total = sum(len(b) for b in batches)
    assert total == 10


def test_summarize_articles_merges_batches():
    articles = make_articles(2)

    mock_message_1 = MagicMock()
    mock_message_1.content = [MagicMock(text="Batch 1 summary")]
    mock_message_1.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_message_2 = MagicMock()
    mock_message_2.content = [MagicMock(text="Batch 2 summary")]
    mock_message_2.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_message_merge = MagicMock()
    mock_message_merge.content = [MagicMock(text="# 今日概述\n\nMerged summary.")]
    mock_message_merge.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [mock_message_1, mock_message_2, mock_message_merge]

    result = summarize_articles(
        articles, mock_client, "claude-sonnet-4-latest", 4096,
        max_chars_per_batch=50,
    )

    assert "今日概述" in result
    assert mock_client.messages.create.call_count == 3
