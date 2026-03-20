# tests/test_pipeline.py
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock
from src.main import run_pipeline
from src.config import Config
from src.database import Database


def make_test_config(tmp_path):
    return Config(
        rsshub_instances=["https://rsshub.app"],
        twitter_accounts=["openai"],
        reddit_subreddits=["MachineLearning"],
        reddit_user_agent="test/1.0",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        gmail_address="test@gmail.com",
        gmail_password="password",
        recipients=["recipient@test.com"],
        schedule_cron="0 8 * * *",
        timezone="Asia/Shanghai",
        anthropic_api_key="sk-test",
        claude_model="claude-sonnet-4-latest",
        max_tokens=4096,
        db_path=str(tmp_path / "test.db"),
        cleanup_days=3,
    )


@patch("src.main.send_email")
@patch("src.main.summarize_articles")
@patch("src.main.fetch_all")
def test_pipeline_skips_when_no_articles(mock_fetch, mock_summarize, mock_send, tmp_path):
    # fetch_all is async, mock it as a coroutine returning empty list
    async def mock_fetch_coro(*args, **kwargs):
        return []
    mock_fetch.side_effect = mock_fetch_coro

    config = make_test_config(tmp_path)
    run_pipeline(config)

    mock_summarize.assert_not_called()
    mock_send.assert_not_called()


@patch("src.main.send_email")
@patch("src.main.summarize_articles")
@patch("src.main.fetch_all")
def test_pipeline_full_flow(mock_fetch, mock_summarize, mock_send, tmp_path):
    from src.models import create_article

    async def mock_fetch_coro(*args, **kwargs):
        return [
            create_article(
                url="https://example.com/1", title="Test Article",
                content="Content", source="twitter", source_name="openai",
                published_at=datetime.now(timezone.utc),
            )
        ]

    mock_fetch.side_effect = mock_fetch_coro
    mock_summarize.return_value = "# 今日概述\n\nTest summary"

    config = make_test_config(tmp_path)
    run_pipeline(config)

    mock_summarize.assert_called_once()
    mock_send.assert_called_once()


@patch("src.main.send_email")
def test_pipeline_retries_unsent_digests(mock_send, tmp_path):
    config = make_test_config(tmp_path)
    db = Database(config.db_path)
    db.init()
    digest_id = db.save_digest("Old Subject", "<h1>Old Digest</h1>")
    db.close()

    async def mock_empty(*args, **kwargs):
        return []

    with patch("src.main.fetch_all", side_effect=mock_empty):
        run_pipeline(config)

    mock_send.assert_called_once()
    # Verify it's now marked as sent
    db2 = Database(config.db_path)
    db2.init()
    assert len(db2.get_unsent_digests()) == 0
    db2.close()
