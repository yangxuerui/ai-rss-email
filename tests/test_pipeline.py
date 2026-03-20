# tests/test_pipeline.py
from unittest.mock import patch, MagicMock
from src.main import run_pipeline
from src.config import Config
from src.database import Database


def make_test_config(tmp_path):
    return Config(
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
        claude_model="claude-sonnet-4-20250514",
        max_tokens=8192,
        exa_api_key="exa-test",
        exa_default_num_results=10,
        max_tool_calls=15,
        max_runtime_seconds=300,
        db_path=str(tmp_path / "test.db"),
        cleanup_days=3,
    )


@patch("src.main.send_email")
@patch("src.main.run_agent")
def test_pipeline_skips_when_agent_returns_empty(mock_agent, mock_send, tmp_path):
    mock_agent.return_value = ""
    config = make_test_config(tmp_path)
    run_pipeline(config)
    mock_send.assert_not_called()


@patch("src.main.send_email")
@patch("src.main.run_agent")
def test_pipeline_full_flow(mock_agent, mock_send, tmp_path):
    mock_agent.return_value = "# 今日概述\n\nAI 有重大突破。"
    config = make_test_config(tmp_path)
    run_pipeline(config)
    mock_send.assert_called_once()


@patch("src.main.send_email")
@patch("src.main.run_agent")
def test_pipeline_agent_failure_does_not_crash(mock_agent, mock_send, tmp_path):
    mock_agent.side_effect = RuntimeError("Agent crashed")
    config = make_test_config(tmp_path)
    run_pipeline(config)  # Should not raise
    mock_send.assert_not_called()


@patch("src.main.send_email")
def test_pipeline_retries_unsent_digests(mock_send, tmp_path):
    config = make_test_config(tmp_path)
    db = Database(config.db_path)
    db.init()
    db.save_digest("Old Subject", "<h1>Old Digest</h1>")
    db.close()

    with patch("src.main.run_agent", return_value=""):
        run_pipeline(config)

    mock_send.assert_called_once()
