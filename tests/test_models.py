# tests/test_models.py
from datetime import datetime, timezone
from src.models import Article, create_article


def test_create_article_computes_url_hash():
    article = create_article(
        url="https://example.com/post/1",
        title="Test Post",
        content="Some content",
        source="twitter",
        source_name="openai",
        published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    assert article.url == "https://example.com/post/1"
    assert article.title == "Test Post"
    assert article.source == "twitter"
    assert len(article.url_hash) == 64  # SHA256 hex digest
    assert article.fetched_at is not None


def test_article_is_frozen():
    article = create_article(
        url="https://example.com/post/1",
        title="Test",
        content="Content",
        source="reddit",
        source_name="MachineLearning",
        published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    try:
        article.title = "Modified"
        assert False, "Should have raised FrozenInstanceError"
    except AttributeError:
        pass


def test_same_url_produces_same_hash():
    a1 = create_article(
        url="https://example.com/post/1",
        title="T1", content="C1", source="twitter",
        source_name="openai",
        published_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    a2 = create_article(
        url="https://example.com/post/1",
        title="T2", content="C2", source="reddit",
        source_name="ML",
        published_at=datetime(2026, 3, 21, tzinfo=timezone.utc),
    )
    assert a1.url_hash == a2.url_hash
