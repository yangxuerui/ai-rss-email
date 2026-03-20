# AI RSS Email Daily Digest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Agent that fetches AI news from X/Reddit via RSS, summarizes with Claude API, and sends daily email digests.

**Architecture:** Single-process Python app using APScheduler for daily cron. Fetcher (async aiohttp) → Processor (SQLite dedup) → Summarizer (Claude API) → EmailSender (Gmail SMTP). Config via YAML + .env.

**Tech Stack:** Python 3.11+, feedparser, aiohttp, anthropic SDK, APScheduler 4, tenacity, SQLite, Jinja2, markdown

**Spec:** `docs/superpowers/specs/2026-03-20-ai-rss-email-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/__init__.py` | Package marker |
| `src/models.py` | Article frozen dataclass |
| `src/config.py` | Load YAML + .env, produce Config object |
| `src/database.py` | SQLite init, insert, query, cleanup |
| `src/fetcher.py` | Async RSS fetch from RSSHub + Reddit |
| `src/processor.py` | Dedup via url_hash, filter by time |
| `src/summarizer.py` | Claude API call, token batching, fallback |
| `src/email_sender.py` | Render HTML email, send via SMTP |
| `src/main.py` | Pipeline orchestration + APScheduler |
| `templates/email.html` | Jinja2 HTML email template |
| `config.yaml` | RSS sources, email, schedule config |
| `.env.example` | Template for secrets |
| `requirements.txt` | Python dependencies |
| `systemd/ai-rss-email.service` | systemd unit file |
| `tests/test_models.py` | Article model tests |
| `tests/test_config.py` | Config loading tests |
| `tests/test_database.py` | Database CRUD tests |
| `tests/test_fetcher.py` | Fetcher tests (mocked HTTP) |
| `tests/test_processor.py` | Dedup/filter tests |
| `tests/test_summarizer.py` | Summarizer tests (mocked Claude) |
| `tests/test_email_sender.py` | Email render/send tests (mocked SMTP) |
| `tests/test_pipeline.py` | Integration test for full pipeline |
| `tests/__init__.py` | Test package marker |
| `.gitignore` | Git ignore rules |

---

### Task 1: Project Scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Initialize git repo**

```bash
cd /Users/yangxuerui/Desktop/ai/rss_email
git init
```

- [ ] **Step 2: Create requirements.txt**

```
feedparser>=6.0
aiohttp>=3.9
anthropic>=0.40
apscheduler>=4.0
tenacity>=8.0
python-dotenv>=1.0
pyyaml>=6.0
jinja2>=3.1
markdown>=3.5
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 3: Create .env.example**

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

- [ ] **Step 4: Create config.yaml**

```yaml
sources:
  twitter:
    rsshub_instances:
      - "https://rsshub.app"
      - "https://rsshub.rssforever.com"
    accounts:
      - openai
      - AnthropicAI
      - GoogleDeepMind
      - MetaAI
      - _akhaliq
      - kaboroevich
      - huggingface
      - LangChainAI
  reddit:
    subreddits:
      - MachineLearning
      - artificial
      - LocalLLaMA
      - ChatGPT
    user_agent: "ai-rss-email/1.0"

email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  recipients:
    - "user1@gmail.com"

schedule:
  cron: "0 8 * * *"
  timezone: "Asia/Shanghai"

claude:
  model: "claude-sonnet-4-latest"
  max_tokens: 4096

database:
  path: "data/articles.db"
  cleanup_days: 3
```

- [ ] **Step 5: Create src/__init__.py and tests/__init__.py**

Empty files.

- [ ] **Step 6: Create .gitignore**

```
__pycache__/
*.pyc
.env
data/
venv/
.pytest_cache/
```

- [ ] **Step 7: Install dependencies and verify**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .env.example config.yaml src/__init__.py tests/__init__.py .gitignore
git commit -m "chore: project scaffold with dependencies and config"
```

---

### Task 2: Article Model

**Files:**
- Create: `src/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for Article creation and url_hash**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models'`

- [ ] **Step 3: Implement models.py**

```python
# src/models.py
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib


@dataclass(frozen=True)
class Article:
    url: str
    url_hash: str
    title: str
    content: str
    source: str
    source_name: str
    published_at: datetime
    fetched_at: datetime


def create_article(
    url: str,
    title: str,
    content: str,
    source: str,
    source_name: str,
    published_at: datetime,
) -> Article:
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return Article(
        url=url,
        url_hash=url_hash,
        title=title,
        content=content,
        source=source,
        source_name=source_name,
        published_at=published_at,
        fetched_at=datetime.now(timezone.utc),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_models.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: add Article dataclass with url_hash generation"
```

---

### Task 3: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for config loading**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement config.py**

```python
# src/config.py
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import dotenv_values


@dataclass(frozen=True)
class Config:
    # Twitter/RSSHub
    rsshub_instances: list[str]
    twitter_accounts: list[str]
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
    # Database
    db_path: str
    cleanup_days: int


def load_config(
    config_path: str = "config.yaml",
    env_path: str = ".env",
) -> Config:
    with open(config_path) as f:
        yaml_data = yaml.safe_load(f)

    env = dotenv_values(env_path)

    required_env = ["ANTHROPIC_API_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD"]
    missing = [k for k in required_env if not env.get(k)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    twitter = yaml_data.get("sources", {}).get("twitter", {})
    reddit = yaml_data.get("sources", {}).get("reddit", {})
    email = yaml_data.get("email", {})
    schedule = yaml_data.get("schedule", {})
    claude = yaml_data.get("claude", {})
    database = yaml_data.get("database", {})

    return Config(
        rsshub_instances=twitter.get("rsshub_instances", []),
        twitter_accounts=twitter.get("accounts", []),
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
        claude_model=claude.get("model", "claude-sonnet-4-latest"),
        max_tokens=claude.get("max_tokens", 4096),
        db_path=database.get("path", "data/articles.db"),
        cleanup_days=database.get("cleanup_days", 3),
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module loading YAML + .env"
```

---

### Task 4: Database Module

**Files:**
- Create: `src/database.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write failing tests for database operations**

```python
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
    # Should not raise on second init (IF NOT EXISTS)
    db.init()


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_database.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement database.py**

```python
# src/database.py
import sqlite3
from datetime import datetime, timezone, timedelta
from src.models import Article


class Database:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def init(self) -> None:
        import os
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                source TEXT,
                source_name TEXT,
                published_at TIMESTAMP,
                fetched_at TIMESTAMP,
                sent_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP NOT NULL,
                subject TEXT NOT NULL,
                html_content TEXT NOT NULL,
                sent_at TIMESTAMP
            )
        """)

    def insert_article(self, article: Article) -> None:
        self._execute(
            """INSERT OR IGNORE INTO articles
               (url_hash, url, title, content, source, source_name, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (article.url_hash, article.url, article.title, article.content,
             article.source, article.source_name, article.published_at, article.fetched_at),
        )

    def article_exists(self, url_hash: str) -> bool:
        cursor = self._execute(
            "SELECT 1 FROM articles WHERE url_hash = ?", (url_hash,)
        )
        return cursor.fetchone() is not None

    def get_unsent_articles(self) -> list[Article]:
        cursor = self._execute(
            "SELECT * FROM articles WHERE sent_at IS NULL ORDER BY published_at DESC"
        )
        return [
            Article(
                url=row["url"], url_hash=row["url_hash"], title=row["title"],
                content=row["content"], source=row["source"],
                source_name=row["source_name"],
                published_at=row["published_at"], fetched_at=row["fetched_at"],
            )
            for row in cursor.fetchall()
        ]

    def mark_articles_sent(self, url_hashes: list[str]) -> None:
        now = datetime.now(timezone.utc)
        for h in url_hashes:
            self._execute(
                "UPDATE articles SET sent_at = ? WHERE url_hash = ?", (now, h)
            )

    def save_digest(self, subject: str, html_content: str) -> int:
        cursor = self._execute(
            "INSERT INTO digests (created_at, subject, html_content) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc), subject, html_content),
        )
        return cursor.lastrowid

    def get_unsent_digests(self) -> list[dict]:
        cursor = self._execute(
            "SELECT id, subject, html_content, created_at FROM digests WHERE sent_at IS NULL"
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_digest_sent(self, digest_id: int) -> None:
        self._execute(
            "UPDATE digests SET sent_at = ? WHERE id = ?",
            (datetime.now(timezone.utc), digest_id),
        )

    def cleanup(self, days: int = 3) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self._execute(
            "DELETE FROM articles WHERE sent_at IS NOT NULL AND fetched_at < ?",
            (cutoff,),
        )
        self._execute(
            "DELETE FROM digests WHERE sent_at IS NOT NULL AND created_at < ?",
            (cutoff,),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_database.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: add database module with articles/digests CRUD and cleanup"
```

---

### Task 5: RSS Fetcher

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: Write failing tests for fetcher**

```python
# tests/test_fetcher.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.fetcher import fetch_twitter_rss, fetch_reddit_rss, fetch_all
from src.config import Config

# Minimal RSS XML for testing
TWITTER_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>@openai</title>
  <item>
    <title>New GPT release</title>
    <link>https://twitter.com/openai/status/123</link>
    <description>We are releasing GPT-5 today</description>
    <pubDate>Thu, 20 Mar 2026 10:00:00 +0000</pubDate>
  </item>
</channel>
</rss>"""

REDDIT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>New paper on transformers</title>
    <link href="https://reddit.com/r/MachineLearning/comments/abc"/>
    <content>Interesting paper about transformers</content>
    <updated>2026-03-20T10:00:00+00:00</updated>
  </entry>
</feed>"""


@pytest.mark.asyncio
async def test_fetch_twitter_rss_parses_articles():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=TWITTER_RSS)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://rsshub.app"],
        account="openai",
    )
    assert len(articles) == 1
    assert articles[0].source == "twitter"
    assert articles[0].source_name == "openai"
    assert "GPT" in articles[0].title


@pytest.mark.asyncio
async def test_fetch_twitter_rss_fallback_on_failure():
    """If first instance fails, try next one."""
    fail_response = AsyncMock()
    fail_response.status = 500

    ok_response = AsyncMock()
    ok_response.status = 200
    ok_response.text = AsyncMock(return_value=TWITTER_RSS)

    call_count = 0

    class FakeCtx:
        def __init__(self, resp):
            self.resp = resp
        async def __aenter__(self):
            return self.resp
        async def __aexit__(self, *args):
            pass

    mock_session = AsyncMock()
    responses = [FakeCtx(fail_response), FakeCtx(ok_response)]
    mock_session.get = MagicMock(side_effect=responses)

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://bad.instance", "https://rsshub.app"],
        account="openai",
    )
    assert len(articles) == 1


@pytest.mark.asyncio
async def test_fetch_reddit_rss_parses_articles():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=REDDIT_RSS)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_reddit_rss(
        session=mock_session,
        subreddit="MachineLearning",
        user_agent="test/1.0",
    )
    assert len(articles) == 1
    assert articles[0].source == "reddit"
    assert articles[0].source_name == "MachineLearning"


@pytest.mark.asyncio
async def test_fetch_twitter_rss_returns_empty_on_malformed_xml():
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="<not valid xml at all")

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_twitter_rss(
        session=mock_session,
        rsshub_instances=["https://rsshub.app"],
        account="openai",
    )
    assert articles == []  # feedparser handles gracefully, returns empty


@pytest.mark.asyncio
async def test_fetch_reddit_rss_returns_empty_on_empty_feed():
    empty_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=empty_rss)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncContextManager(mock_response))

    articles = await fetch_reddit_rss(
        session=mock_session,
        subreddit="MachineLearning",
        user_agent="test/1.0",
    )
    assert articles == []


class AsyncContextManager:
    """Helper to mock async context manager for aiohttp responses."""
    def __init__(self, return_value):
        self.return_value = return_value
    async def __aenter__(self):
        return self.return_value
    async def __aexit__(self, *args):
        pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_fetcher.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement fetcher.py**

```python
# src/fetcher.py
import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import Article, create_article

logger = logging.getLogger(__name__)


async def fetch_twitter_rss(
    session: aiohttp.ClientSession,
    rsshub_instances: list[str],
    account: str,
) -> list[Article]:
    for instance in rsshub_instances:
        url = f"{instance.rstrip('/')}/twitter/user/{account}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(f"RSSHub {instance} returned {resp.status} for {account}")
                    continue
                text = await resp.text()
                return _parse_feed(text, source="twitter", source_name=account)
        except Exception as e:
            logger.warning(f"RSSHub {instance} failed for {account}: {e}")
            continue

    logger.error(f"All RSSHub instances failed for {account}")
    return []


async def fetch_reddit_rss(
    session: aiohttp.ClientSession,
    subreddit: str,
    user_agent: str,
) -> list[Article]:
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    headers = {"User-Agent": user_agent}
    try:
        return await _fetch_reddit_with_retry(session, url, headers, subreddit)
    except Exception as e:
        logger.error(f"Reddit fetch failed for r/{subreddit} after retries: {e}")
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _fetch_reddit_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
    subreddit: str,
) -> list[Article]:
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status == 429:
            raise Exception(f"Reddit rate limited (429) for r/{subreddit}")
        if resp.status != 200:
            logger.warning(f"Reddit returned {resp.status} for r/{subreddit}")
            return []
        text = await resp.text()
        return _parse_feed(text, source="reddit", source_name=subreddit)


async def fetch_all(
    rsshub_instances: list[str],
    twitter_accounts: list[str],
    reddit_subreddits: list[str],
    reddit_user_agent: str,
) -> list[Article]:
    articles: list[Article] = []

    async with aiohttp.ClientSession() as session:
        # Twitter: concurrent
        twitter_tasks = [
            fetch_twitter_rss(session, rsshub_instances, account)
            for account in twitter_accounts
        ]
        twitter_results = await asyncio.gather(*twitter_tasks, return_exceptions=True)
        for result in twitter_results:
            if isinstance(result, list):
                articles.extend(result)
            else:
                logger.error(f"Twitter fetch error: {result}")

        # Reddit: sequential with 1s delay
        for subreddit in reddit_subreddits:
            result = await fetch_reddit_rss(session, subreddit, reddit_user_agent)
            articles.extend(result)
            if subreddit != reddit_subreddits[-1]:
                await asyncio.sleep(1)

    logger.info(f"Fetched {len(articles)} total articles")
    return articles


def _parse_feed(text: str, source: str, source_name: str) -> list[Article]:
    feed = feedparser.parse(text)
    articles = []
    for entry in feed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            from time import mktime
            pub_dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
        else:
            pub_dt = datetime.now(timezone.utc)

        link = entry.get("link", "")
        title = entry.get("title", "")
        content = entry.get("description") or entry.get("summary", "")

        if link:
            articles.append(
                create_article(
                    url=link,
                    title=title,
                    content=content,
                    source=source,
                    source_name=source_name,
                    published_at=pub_dt,
                )
            )
    return articles
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_fetcher.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add async RSS fetcher with RSSHub fallback and Reddit rate limiting"
```

---

### Task 6: Processor Module

**Files:**
- Create: `src/processor.py`
- Create: `tests/test_processor.py`

- [ ] **Step 1: Write failing tests for processor**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_processor.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement processor.py**

```python
# src/processor.py
import logging
from datetime import datetime, timezone, timedelta

from src.database import Database
from src.models import Article

logger = logging.getLogger(__name__)


def process_articles(
    articles: list[Article],
    db: Database,
    max_age_hours: int = 24,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    new_articles = []

    for article in articles:
        if article.published_at < cutoff:
            continue
        if db.article_exists(article.url_hash):
            continue
        db.insert_article(article)
        new_articles.append(article)

    logger.info(
        f"Processed {len(articles)} articles: "
        f"{len(new_articles)} new, {len(articles) - len(new_articles)} filtered"
    )
    return new_articles
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_processor.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/processor.py tests/test_processor.py
git commit -m "feat: add processor module with dedup and time filtering"
```

---

### Task 7: Summarizer Module

**Files:**
- Create: `src/summarizer.py`
- Create: `tests/test_summarizer.py`

- [ ] **Step 1: Write failing tests for summarizer**

```python
# tests/test_summarizer.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from src.summarizer import summarize_articles, _build_prompt, _truncate_content
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
    from src.summarizer import _batch_articles
    articles = make_articles(10)
    # Use a small char limit to force multiple batches
    batches = _batch_articles(articles, max_chars_per_batch=200)
    assert len(batches) > 1
    # All articles should be in some batch
    total = sum(len(b) for b in batches)
    assert total == 10


def test_summarize_articles_merges_batches():
    """When articles are split into batches, summaries are merged."""
    articles = make_articles(2)

    mock_message_1 = MagicMock()
    mock_message_1.content = [MagicMock(text="Batch 1 summary")]
    mock_message_2 = MagicMock()
    mock_message_2.content = [MagicMock(text="# 今日概述\n\nMerged summary.")]

    mock_client = MagicMock()
    # First call: batch summary, Second call: merge
    mock_client.messages.create.side_effect = [mock_message_1, mock_message_2]

    # Force batching by using a very small char limit
    result = summarize_articles(
        articles, mock_client, "claude-sonnet-4-latest", 4096,
        max_chars_per_batch=50,
    )

    assert "今日概述" in result
    assert mock_client.messages.create.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_summarizer.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement summarizer.py**

```python
# src/summarizer.py
import json
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import Article

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是一个 AI 科技新闻编辑，擅长将英文科技新闻整理为简洁的中文日报。"

USER_PROMPT_TEMPLATE = """请根据以下今日新闻，生成一份中文 AI 日报：

1. 先写一段 3-5 句的「今日概述」，总结今天最重要的 AI 动态
2. 然后按来源分类，每条新闻给出：
   - 标题
   - 一句话中文摘要
   - 原文链接

新闻列表：
{articles_json}"""


def _truncate_content(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _build_prompt(articles: list[Article]) -> str:
    items = [
        {
            "title": a.title,
            "content": _truncate_content(a.content),
            "url": a.url,
            "source": a.source,
            "source_name": a.source_name,
        }
        for a in articles
    ]
    return USER_PROMPT_TEMPLATE.format(articles_json=json.dumps(items, ensure_ascii=False, indent=2))


def _build_fallback(articles: list[Article]) -> str:
    lines = ["# AI 日报（摘要生成失败，以下为原始列表）\n"]
    for a in articles:
        lines.append(f"- **{a.title}** ({a.source}/{a.source_name})")
        lines.append(f"  {_truncate_content(a.content, 200)}")
        lines.append(f"  [原文链接]({a.url})\n")
    return "\n".join(lines)


def _batch_articles(
    articles: list[Article],
    max_chars_per_batch: int = 80000,
) -> list[list[Article]]:
    """Split articles into batches based on estimated character count."""
    batches: list[list[Article]] = []
    current_batch: list[Article] = []
    current_chars = 0

    for article in articles:
        article_chars = len(article.title) + len(_truncate_content(article.content)) + len(article.url) + 100
        if current_batch and current_chars + article_chars > max_chars_per_batch:
            batches.append(current_batch)
            current_batch = []
            current_chars = 0
        current_batch.append(article)
        current_chars += article_chars

    if current_batch:
        batches.append(current_batch)

    return batches


def summarize_articles(
    articles: list[Article],
    client,  # anthropic.Anthropic
    model: str,
    max_tokens: int,
    max_chars_per_batch: int = 80000,
) -> str:
    try:
        batches = _batch_articles(articles, max_chars_per_batch)

        if len(batches) == 1:
            prompt = _build_prompt(batches[0])
            return _call_claude(client, model, max_tokens, prompt)

        # Multiple batches: summarize each, then merge
        logger.info(f"Splitting {len(articles)} articles into {len(batches)} batches")
        batch_summaries = []
        for i, batch in enumerate(batches):
            prompt = _build_prompt(batch)
            summary = _call_claude(client, model, max_tokens, prompt)
            batch_summaries.append(summary)
            logger.info(f"Batch {i+1}/{len(batches)} summarized")

        # Merge batch summaries
        merge_prompt = (
            "以下是分批生成的 AI 日报摘要，请合并为一份完整的中文 AI 日报。\n"
            "保持「今日概述」+ 分类新闻列表的格式，去除重复内容。\n\n"
            + "\n\n---\n\n".join(batch_summaries)
        )
        return _call_claude(client, model, max_tokens, merge_prompt)

    except Exception as e:
        logger.error(f"Claude API failed after retries: {e}")
        logger.info("Falling back to raw article list")
        return _build_fallback(articles)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _call_claude(client, model: str, max_tokens: int, prompt: str) -> str:
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    result = message.content[0].text
    logger.info(f"Claude API usage: {message.usage.input_tokens} input, {message.usage.output_tokens} output tokens")
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_summarizer.py -v
```
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/summarizer.py tests/test_summarizer.py
git commit -m "feat: add summarizer with Claude API integration and fallback"
```

---

### Task 8: Email Sender Module

**Files:**
- Create: `src/email_sender.py`
- Create: `templates/email.html`
- Create: `tests/test_email_sender.py`

- [ ] **Step 1: Write failing tests for email sender**

```python
# tests/test_email_sender.py
from unittest.mock import patch, MagicMock
from src.email_sender import render_email, send_email, generate_subject
from datetime import date


def test_render_email_produces_html():
    markdown_content = "# 今日概述\n\nAI 领域有重大突破。\n\n- **标题1** 摘要"
    html = render_email(markdown_content)
    assert "<h1>" in html or "<h1" in html
    assert "今日概述" in html
    assert "<!DOCTYPE html>" in html  # Full HTML document


def test_generate_subject():
    subject = generate_subject(date(2026, 3, 20), "GPT-5发布, Claude更新")
    assert "AI 日报" in subject
    assert "2026-03-20" in subject


def test_send_email_calls_smtp():
    with patch("src.email_sender.smtplib.SMTP") as mock_smtp_class:
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        send_email(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            sender="test@gmail.com",
            password="password",
            recipients=["a@test.com", "b@test.com"],
            subject="Test Subject",
            html_content="<h1>Hello</h1>",
        )

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@gmail.com", "password")
        assert mock_smtp.send_message.call_count == 2  # One per recipient
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_email_sender.py -v
```
Expected: FAIL

- [ ] **Step 3: Create email HTML template**

```html
<!-- templates/email.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 700px;
      margin: 0 auto;
      padding: 20px;
      background-color: #f5f5f5;
    }
    .container {
      background: #fff;
      border-radius: 8px;
      padding: 30px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    h1 { color: #1a1a1a; font-size: 22px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px; }
    h2 { color: #2c2c2c; font-size: 18px; margin-top: 24px; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    ul { padding-left: 20px; }
    li { margin-bottom: 8px; }
    .footer {
      margin-top: 30px;
      padding-top: 15px;
      border-top: 1px solid #e0e0e0;
      font-size: 12px;
      color: #888;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="container">
    {{ content }}
    <div class="footer">
      由 AI RSS Email Agent 自动生成 | Powered by Claude
    </div>
  </div>
</body>
</html>
```

- [ ] **Step 4: Implement email_sender.py**

```python
# src/email_sender.py
import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import markdown
from jinja2 import Template
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email.html"


def generate_subject(today: date, highlight: str = "") -> str:
    base = f"「AI 日报」{today.isoformat()}"
    if highlight:
        return f"{base} | {highlight}"
    return base


def render_email(markdown_content: str) -> str:
    html_body = markdown.markdown(markdown_content, extensions=["extra", "nl2br"])
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)
    return template.render(content=html_body)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_email(
    smtp_host: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipients: list[str],
    subject: str,
    html_content: str,
) -> None:
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)

        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            server.send_message(msg)
            logger.info(f"Email sent to {recipient}")
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/test_email_sender.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/email_sender.py templates/email.html tests/test_email_sender.py
git commit -m "feat: add email sender with HTML rendering and Gmail SMTP"
```

---

### Task 9: Main Pipeline + Scheduler

**Files:**
- Create: `src/main.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing integration test for pipeline**

```python
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


# fetch_all is async, so we need to mock it as a coroutine
async def _empty_fetch(*args, **kwargs):
    return []


@patch("src.main.send_email")
@patch("src.main.summarize_articles")
@patch("src.main.fetch_all", new_callable=lambda: lambda: AsyncMock(return_value=[]))
def test_pipeline_skips_when_no_articles(mock_fetch, mock_summarize, mock_send, tmp_path):
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

    # Insert an unsent digest
    digest_id = db.save_digest("Old Subject", "<h1>Old Digest</h1>")
    db.close()

    # Patch fetch_all to return empty (no new articles)
    async def mock_empty(*args, **kwargs):
        return []

    with patch("src.main.fetch_all", side_effect=mock_empty):
        run_pipeline(config)

    # The unsent digest should have been sent
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["subject"] == "Old Subject"

    # Verify it's now marked as sent
    db2 = Database(config.db_path)
    db2.init()
    assert len(db2.get_unsent_digests()) == 0
    db2.close()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_pipeline.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement main.py**

```python
# src/main.py
import asyncio
import logging
import sys
from datetime import date

import anthropic
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_config, Config
from src.database import Database
from src.email_sender import generate_subject, render_email, send_email
from src.fetcher import fetch_all
from src.processor import process_articles
from src.summarizer import summarize_articles

logger = logging.getLogger(__name__)


def run_pipeline(config: Config) -> None:
    db = Database(config.db_path)
    db.init()

    try:
        # Step 1: Retry unsent digests
        _retry_unsent_digests(db, config)

        # Step 2: Fetch
        logger.info("Fetching RSS feeds...")
        articles = asyncio.run(
            fetch_all(
                rsshub_instances=config.rsshub_instances,
                twitter_accounts=config.twitter_accounts,
                reddit_subreddits=config.reddit_subreddits,
                reddit_user_agent=config.reddit_user_agent,
            )
        )

        # Step 3: Process
        new_articles = process_articles(articles, db)

        if not new_articles:
            logger.info("No new articles found, skipping digest")
            db.cleanup(config.cleanup_days)
            return

        # Step 4: Summarize
        logger.info(f"Summarizing {len(new_articles)} articles with Claude...")
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        summary_md = summarize_articles(
            new_articles, client, config.claude_model, config.max_tokens
        )

        # Step 5: Render
        html_content = render_email(summary_md)
        subject = generate_subject(date.today(), _extract_highlight(summary_md))
        digest_id = db.save_digest(subject, html_content)

        # Step 6: Send
        logger.info(f"Sending digest to {len(config.recipients)} recipients...")
        send_email(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            sender=config.gmail_address,
            password=config.gmail_password,
            recipients=config.recipients,
            subject=subject,
            html_content=html_content,
        )

        # Step 7: Mark
        db.mark_articles_sent([a.url_hash for a in new_articles])
        db.mark_digest_sent(digest_id)
        logger.info("Digest sent successfully")

        # Step 8: Cleanup
        db.cleanup(config.cleanup_days)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
    finally:
        db.close()


def _retry_unsent_digests(db: Database, config: Config) -> None:
    unsent = db.get_unsent_digests()
    for digest in unsent:
        logger.info(f"Retrying unsent digest {digest['id']}: {digest['subject']}")
        try:
            send_email(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                sender=config.gmail_address,
                password=config.gmail_password,
                recipients=config.recipients,
                subject=digest["subject"],
                html_content=digest["html_content"],
            )
            db.mark_digest_sent(digest["id"])
            logger.info(f"Unsent digest {digest['id']} sent successfully")
        except Exception as e:
            logger.error(f"Retry failed for digest {digest['id']}: {e}")


def _extract_highlight(markdown_text: str) -> str:
    lines = markdown_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:50]
    return ""


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    logger.info("AI RSS Email Agent started")

    # Parse cron expression: "0 8 * * *" -> minute=0, hour=8
    cron_parts = config.schedule_cron.split()
    trigger = CronTrigger(
        minute=cron_parts[0],
        hour=cron_parts[1],
        day=cron_parts[2] if cron_parts[2] != "*" else None,
        month=cron_parts[3] if cron_parts[3] != "*" else None,
        day_of_week=cron_parts[4] if cron_parts[4] != "*" else None,
        timezone=config.timezone,
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, trigger, args=[config], id="daily_digest")

    logger.info(f"Scheduled daily digest: {config.schedule_cron} ({config.timezone})")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_pipeline.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/main.py tests/test_pipeline.py
git commit -m "feat: add main pipeline with scheduler and retry logic"
```

---

### Task 10: systemd Service + Deployment Files

**Files:**
- Create: `systemd/ai-rss-email.service`

- [ ] **Step 1: Create systemd service file**

```ini
[Unit]
Description=AI RSS Email Daily Digest
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/ai-rss-email
ExecStart=/opt/ai-rss-email/venv/bin/python -m src.main
Restart=on-failure
RestartSec=30
EnvironmentFile=/opt/ai-rss-email/.env

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Commit**

```bash
git add systemd/ai-rss-email.service
git commit -m "chore: add systemd service file for deployment"
```

---

### Task 11: Run All Tests + Final Verification

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 2: Run a manual dry-run of the pipeline**

```bash
# Create a .env with real credentials, then:
python -c "
from src.config import load_config
from src.main import run_pipeline
config = load_config()
run_pipeline(config)
"
```

- [ ] **Step 3: Final commit with all files**

```bash
git add -A
git status
git commit -m "feat: AI RSS Email Daily Digest Agent complete"
```
