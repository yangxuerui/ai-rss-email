# tests/test_config.py
import os
import tempfile
from pathlib import Path
from src.config import load_config

SAMPLE_YAML = """
sources:
  twitter:
    rsshub_instances:
      - "https://rsshub.app"
    accounts:
      - openai
      - AnthropicAI
  reddit:
    subreddits:
      - MachineLearning
    user_agent: "ai-rss-email/1.0"

email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  recipients:
    - "test@gmail.com"

schedule:
  cron: "0 8 * * *"
  timezone: "Asia/Shanghai"

claude:
  model: "claude-sonnet-4-latest"
  max_tokens: 4096

database:
  path: "data/articles.db"
  cleanup_days: 3
"""


def test_load_config_from_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(SAMPLE_YAML)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-test-key\n"
        "GMAIL_ADDRESS=sender@gmail.com\n"
        "GMAIL_APP_PASSWORD=test-password\n"
    )

    config = load_config(str(config_file), str(env_file))

    assert config.twitter_accounts == ["openai", "AnthropicAI"]
    assert config.rsshub_instances == ["https://rsshub.app"]
    assert config.reddit_subreddits == ["MachineLearning"]
    assert config.reddit_user_agent == "ai-rss-email/1.0"
    assert config.smtp_host == "smtp.gmail.com"
    assert config.smtp_port == 587
    assert config.gmail_address == "sender@gmail.com"
    assert config.gmail_password == "test-password"
    assert config.anthropic_api_key == "sk-test-key"
    assert config.claude_model == "claude-sonnet-4-latest"
    assert config.recipients == ["test@gmail.com"]
    assert config.schedule_cron == "0 8 * * *"
    assert config.timezone == "Asia/Shanghai"
    assert config.db_path == "data/articles.db"
    assert config.cleanup_days == 3


def test_load_config_missing_env_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(SAMPLE_YAML)
    env_file = tmp_path / ".env"
    env_file.write_text("")  # missing required keys

    try:
        load_config(str(config_file), str(env_file))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "ANTHROPIC_API_KEY" in str(e)
