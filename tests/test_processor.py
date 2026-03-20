# tests/test_processor.py
from datetime import datetime, timezone, timedelta
from src.processor import process_articles
from src.database import Database
from src.models import create_article


def make_article(url="https://example.com/1", hours_ago=0):
    return create_article(
        url=url, title="Test", content="Content",
        source="twitter", source_name="openai",
        published_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


def test_process_filters_duplicates(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    existing = make_article(url="https://example.com/old")
    db.insert_article(existing)
    articles = [
        make_article(url="https://example.com/old"),  # duplicate
        make_article(url="https://example.com/new"),  # new
    ]
    new_articles = process_articles(articles, db)
    assert len(new_articles) == 1
    assert new_articles[0].url == "https://example.com/new"


def test_process_filters_old_articles(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    articles = [
        make_article(url="https://example.com/recent", hours_ago=2),
        make_article(url="https://example.com/old", hours_ago=30),
    ]
    new_articles = process_articles(articles, db)
    assert len(new_articles) == 1
    assert new_articles[0].url == "https://example.com/recent"


def test_process_inserts_new_articles_to_db(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    articles = [make_article(url="https://example.com/new")]
    process_articles(articles, db)
    assert db.article_exists(articles[0].url_hash) is True
