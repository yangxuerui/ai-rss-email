# src/config.py
from dataclasses import dataclass

import os

import yaml
from dotenv import dotenv_values


@dataclass(frozen=True)
class Config:
    # Reddit
    reddit_subreddits: list[str]
    reddit_user_agent: str
    # Email
    smtp_host: str
    smtp_port: int
    gmail_address: str
    gmail_password: str
    recipients: list[str]
    # Schedule
    schedule_cron: str
    timezone: str
    # Claude
    anthropic_api_key: str
    claude_model: str
    max_tokens: int
    # Exa
    exa_api_key: str
    exa_default_num_results: int
    # Agent
    max_tool_calls: int
    max_runtime_seconds: int
    # Database
    db_path: str
    cleanup_days: int


def load_config(
    config_path: str = "config.yaml",
    env_path: str = ".env",
) -> Config:
    with open(config_path) as f:
        yaml_data = yaml.safe_load(f)

    env = {**dotenv_values(env_path), **os.environ}

    required_env = ["ANTHROPIC_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EXA_API_KEY"]
    missing = [k for k in required_env if not env.get(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    reddit = yaml_data.get("sources", {}).get("reddit", {})
    email = yaml_data.get("email", {})
    schedule = yaml_data.get("schedule", {})
    claude = yaml_data.get("claude", {})
    agent = yaml_data.get("agent", {})
    exa = yaml_data.get("exa", {})
    database = yaml_data.get("database", {})

    return Config(
        reddit_subreddits=reddit.get("subreddits", []),
        reddit_user_agent=reddit.get("user_agent", "ai-rss-email/1.0"),
        smtp_host=email.get("smtp_host", "smtp.gmail.com"),
        smtp_port=email.get("smtp_port", 587),
        gmail_address=env["GMAIL_ADDRESS"],
        gmail_password=env["GMAIL_APP_PASSWORD"],
        recipients=email.get("recipients", []),
        schedule_cron=schedule.get("cron", "0 8 * * *"),
        timezone=schedule.get("timezone", "Asia/Shanghai"),
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        claude_model=claude.get("model", "claude-sonnet-4-20250514"),
        max_tokens=claude.get("max_tokens", 8192),
        exa_api_key=env["EXA_API_KEY"],
        exa_default_num_results=exa.get("default_num_results", 10),
        max_tool_calls=agent.get("max_tool_calls", 15),
        max_runtime_seconds=agent.get("max_runtime_seconds", 300),
        db_path=database.get("path", "data/articles.db"),
        cleanup_days=database.get("cleanup_days", 3),
    )
