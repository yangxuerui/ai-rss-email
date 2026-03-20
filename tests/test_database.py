# tests/test_database.py
from datetime import datetime, timezone, timedelta
from src.database import Database
from src.models import create_article


def make_article(url="https://example.com/1", source="twitter", source_name="openai"):
    return create_article(
        url=url, title="Test", content="Content",
        source=source, source_name=source_name,
        published_at=datetime.now(timezone.utc),
    )


def test_init_creates_tables(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    db.init()  # Should not raise on second init


def test_insert_and_exists(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    article = make_article()
    db.insert_article(article)
    assert db.article_exists(article.url_hash) is True
    assert db.article_exists("nonexistent") is False


def test_insert_duplicate_is_ignored(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    article = make_article()
    db.insert_article(article)
    db.insert_article(article)  # Should not raise


def test_get_unsent_articles(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    a1 = make_article(url="https://example.com/1")
    a2 = make_article(url="https://example.com/2")
    db.insert_article(a1)
    db.insert_article(a2)
    db.mark_articles_sent([a1.url_hash])

    unsent = db.get_unsent_articles()
    assert len(unsent) == 1
    assert unsent[0].url_hash == a2.url_hash


def test_save_and_get_unsent_digest(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    digest_id = db.save_digest("Test Subject", "<h1>Hello</h1>")
    unsent = db.get_unsent_digests()
    assert len(unsent) == 1
    assert unsent[0]["id"] == digest_id
    assert unsent[0]["subject"] == "Test Subject"

    db.mark_digest_sent(digest_id)
    assert len(db.get_unsent_digests()) == 0


def test_cleanup_old_records(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.init()
    article = make_article()
    db.insert_article(article)
    db.mark_articles_sent([article.url_hash])

    # Manually backdate fetched_at to 5 days ago
    db._execute(
        "UPDATE articles SET fetched_at = ? WHERE url_hash = ?",
        (datetime.now(timezone.utc) - timedelta(days=5), article.url_hash),
    )
    db.cleanup(days=3)

    assert db.article_exists(article.url_hash) is False
