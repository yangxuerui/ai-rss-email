# tests/test_config.py
from src.config import load_config

SAMPLE_YAML = """
sources:
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
  model: "claude-sonnet-4-20250514"
  max_tokens: 8192

agent:
  max_tool_calls: 15
  max_runtime_seconds: 300

exa:
  default_num_results: 10

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
        "EXA_API_KEY=exa-test-key\n"
    )
    config = load_config(str(config_file), str(env_file))
    assert config.reddit_subreddits == ["MachineLearning"]
    assert config.exa_api_key == "exa-test-key"
    assert config.max_tool_calls == 15
    assert config.max_runtime_seconds == 300
    assert config.exa_default_num_results == 10
    assert config.claude_model == "claude-sonnet-4-20250514"
    assert config.max_tokens == 8192


def test_load_config_missing_env_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(SAMPLE_YAML)
    env_file = tmp_path / ".env"
    env_file.write_text("")
    try:
        load_config(str(config_file), str(env_file))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "ANTHROPIC_API_KEY" in str(e)
