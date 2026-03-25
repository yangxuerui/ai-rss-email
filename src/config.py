# src/config.py
from dataclasses import dataclass

import os

import yaml
from dotenv import dotenv_values


@dataclass(frozen=True)
class RssFeedConfig:
    name: str
    url: str
    source: str


@dataclass(frozen=True)
class Config:
    # RSSHub
    rsshub_base_url: str
    # Reddit
    reddit_subreddits: list[str]
    reddit_user_agent: str
    # RSS Feeds
    rss_feeds: list[RssFeedConfig]
    # Email
    smtp_host: str
    smtp_port: int
    gmail_address: str
    gmail_password: str
    recipients: list[str]
    # Schedule
    schedule_cron: str
    timezone: str
    # LLM (Anthropic-compatible: Claude / ZhipuAI)
    llm_api_key: str
    llm_base_url: str
    llm_model: str
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

    required_env = ["LLM_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "EXA_API_KEY"]
    missing = [k for k in required_env if not env.get(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    sources = yaml_data.get("sources", {})
    rsshub = sources.get("rsshub", {})
    reddit = sources.get("reddit", {})
    raw_feeds = sources.get("rss_feeds", [])
    email = yaml_data.get("email", {})
    schedule = yaml_data.get("schedule", {})
    llm = yaml_data.get("llm", {})
    agent = yaml_data.get("agent", {})
    exa = yaml_data.get("exa", {})
    database = yaml_data.get("database", {})

    rsshub_base = rsshub.get("base_url", "")
    rss_feeds = []
    for feed in raw_feeds:
        if "url" in feed:
            url = feed["url"]
        elif "url_path" in feed and rsshub_base:
            url = rsshub_base.rstrip("/") + feed["url_path"]
        else:
            continue
        rss_feeds.append(RssFeedConfig(
            name=feed.get("name", ""),
            url=url,
            source=feed.get("source", "rss"),
        ))

    return Config(
        rsshub_base_url=rsshub_base,
        reddit_subreddits=reddit.get("subreddits", []),
        reddit_user_agent=reddit.get("user_agent", "ai-rss-email/1.0"),
        rss_feeds=rss_feeds,
        smtp_host=email.get("smtp_host", "smtp.gmail.com"),
        smtp_port=email.get("smtp_port", 587),
        gmail_address=env["GMAIL_ADDRESS"],
        gmail_password=env["GMAIL_APP_PASSWORD"],
        recipients=email.get("recipients", []),
        schedule_cron=schedule.get("cron", "0 8 * * *"),
        timezone=schedule.get("timezone", "Asia/Shanghai"),
        llm_api_key=env["LLM_API_KEY"],
        llm_base_url=llm.get("base_url", "https://open.bigmodel.cn/api/anthropic"),
        llm_model=llm.get("model", "glm-4.5-flash"),
        max_tokens=llm.get("max_tokens", 8192),
        exa_api_key=env["EXA_API_KEY"],
        exa_default_num_results=exa.get("default_num_results", 10),
        max_tool_calls=agent.get("max_tool_calls", 15),
        max_runtime_seconds=agent.get("max_runtime_seconds", 300),
        db_path=database.get("path", "data/articles.db"),
        cleanup_days=database.get("cleanup_days", 3),
    )
