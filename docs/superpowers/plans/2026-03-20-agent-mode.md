# Agent Mode Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the summarizer from one-shot Claude call to Agent mode with tool_use, using Exa search for news/tweets and existing Reddit RSS.

**Architecture:** Claude Agent loop with 4 tools (exa_search_news, exa_search_tweets, exa_get_contents, fetch_reddit_rss). Agent autonomously searches, verifies, and generates digest. Fallback to old summarizer on Agent failure.

**Tech Stack:** anthropic SDK (tool_use), exa-py, existing feedparser/aiohttp

**Spec:** `docs/superpowers/specs/2026-03-20-agent-mode-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/tools.py` | **New** — Tool implementations (Exa search, Exa contents, Reddit RSS wrapper) |
| `src/agent.py` | **New** — Agent loop, tool definitions, safety limits, execute_tool dispatch |
| `src/config.py` | **Modify** — Add exa/agent config fields, remove twitter/rsshub fields |
| `src/main.py` | **Modify** — Replace fetch→process→summarize with agent call, add fallback |
| `src/fetcher.py` | **Modify** — Remove Twitter/RSSHub code, keep Reddit only |
| `config.yaml` | **Modify** — Remove twitter section, add agent/exa sections |
| `.env.example` | **Modify** — Add EXA_API_KEY |
| `requirements.txt` | **Modify** — Add exa-py |
| `tests/test_tools.py` | **New** — Tool unit tests with mocked Exa/RSS |
| `tests/test_agent.py` | **New** — Agent loop tests with mocked Claude responses |
| `tests/test_config.py` | **Modify** — Adapt to new Config fields |
| `tests/test_fetcher.py` | **Modify** — Remove Twitter tests |
| `tests/test_pipeline.py` | **Modify** — Adapt to Agent-based pipeline |

---

### Task 1: Update Config + Dependencies

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`
- Modify: `config.yaml`
- Modify: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 1: Update requirements.txt — add exa-py**

Add `exa-py>=2.0` to requirements.txt.

- [ ] **Step 2: Update .env.example — add EXA_API_KEY**

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
EXA_API_KEY=your-exa-api-key
```

- [ ] **Step 3: Update config.yaml — remove twitter, add agent/exa**

```yaml
sources:
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
    - "yangxuerui0103@gmail.com"
    - "yangxuerui0103@163.com"

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
```

- [ ] **Step 4: Write failing test — update tests/test_config.py**

Replace the existing test with new Config fields:

```python
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
        "ANTHROPIC_API_KEY=sk-test-key\\n"
        "GMAIL_ADDRESS=sender@gmail.com\\n"
        "GMAIL_APP_PASSWORD=test-password\\n"
        "EXA_API_KEY=exa-test-key\\n"
    )

    config = load_config(str(config_file), str(env_file))

    assert config.reddit_subreddits == ["MachineLearning"]
    assert config.exa_api_key == "exa-test-key"
    assert config.max_tool_calls == 15
    assert config.max_runtime_seconds == 300
    assert config.exa_default_num_results == 10
    assert config.claude_model == "claude-sonnet-4-20250514"
    assert config.max_tokens == 8192
    assert not hasattr(config, "rsshub_instances")
    assert not hasattr(config, "twitter_accounts")


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
```

- [ ] **Step 5: Run test — verify FAIL**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 6: Update src/config.py**

```python
# src/config.py
from dataclasses import dataclass

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

    env = dotenv_values(env_path)

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
```

- [ ] **Step 7: Run test — verify PASS**

```bash
pytest tests/test_config.py -v
```

- [ ] **Step 8: Install exa-py and commit**

```bash
source venv/bin/activate && pip install exa-py>=2.0
git add src/config.py tests/test_config.py config.yaml .env.example requirements.txt
git commit -m "refactor: update config for Agent mode — add exa/agent fields, remove twitter"
```

---

### Task 2: Tools Module

**Files:**
- Create: `src/tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for tools**

```python
# tests/test_tools.py
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from src.tools import execute_exa_search_news, execute_exa_search_tweets, execute_exa_get_contents, execute_fetch_reddit_rss


def _make_exa_result(title="Test Article", url="https://example.com/1", highlights=None):
    result = MagicMock()
    result.title = title
    result.url = url
    result.highlights = highlights or ["This is a highlight"]
    result.published_date = "2026-03-20T10:00:00Z"
    return result


def test_exa_search_news_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="AI News", url="https://news.com/1")]
    mock_exa.search_and_contents.return_value = mock_response

    result = execute_exa_search_news(mock_exa, "AI news", num_results=5)
    parsed = json.loads(result)

    assert len(parsed) == 1
    assert parsed[0]["title"] == "AI News"
    assert parsed[0]["url"] == "https://news.com/1"
    mock_exa.search_and_contents.assert_called_once()


def test_exa_search_news_returns_error_on_failure():
    mock_exa = MagicMock()
    mock_exa.search_and_contents.side_effect = Exception("API Error")

    result = execute_exa_search_news(mock_exa, "AI news", num_results=5)
    parsed = json.loads(result)

    assert "error" in parsed


def test_exa_search_tweets_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="AI Tweet", url="https://x.com/1")]
    mock_exa.search_and_contents.return_value = mock_response

    result = execute_exa_search_tweets(mock_exa, "Claude AI", num_results=5)
    parsed = json.loads(result)

    assert len(parsed) == 1
    assert parsed[0]["title"] == "AI Tweet"


def test_exa_get_contents_returns_formatted_results():
    mock_exa = MagicMock()
    mock_response = MagicMock()
    mock_response.results = [_make_exa_result(title="Full Article", url="https://example.com/full")]
    mock_exa.get_contents.return_value = mock_response

    result = execute_exa_get_contents(mock_exa, ["https://example.com/full"])
    parsed = json.loads(result)

    assert len(parsed) == 1
    assert parsed[0]["title"] == "Full Article"


def test_exa_get_contents_returns_error_on_failure():
    mock_exa = MagicMock()
    mock_exa.get_contents.side_effect = Exception("Timeout")

    result = execute_exa_get_contents(mock_exa, ["https://example.com/1"])
    parsed = json.loads(result)

    assert "error" in parsed


def test_fetch_reddit_rss_returns_formatted_results():
    with patch("src.tools.asyncio") as mock_asyncio:
        from src.models import create_article
        articles = [
            create_article(
                url="https://reddit.com/r/ML/1", title="ML Post",
                content="Content", source="reddit", source_name="MachineLearning",
                published_at=datetime.now(timezone.utc),
            )
        ]
        mock_asyncio.run.return_value = articles

        result = execute_fetch_reddit_rss(["MachineLearning"], "test/1.0")
        parsed = json.loads(result)

        assert len(parsed) == 1
        assert parsed[0]["title"] == "ML Post"


def test_fetch_reddit_rss_returns_error_on_failure():
    with patch("src.tools.asyncio") as mock_asyncio:
        mock_asyncio.run.side_effect = Exception("Network error")

        result = execute_fetch_reddit_rss(["MachineLearning"], "test/1.0")
        parsed = json.loads(result)

        assert "error" in parsed
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
pytest tests/test_tools.py -v
```

- [ ] **Step 3: Implement src/tools.py**

```python
# src/tools.py
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from exa_py import Exa

from src.fetcher import fetch_reddit_rss as _fetch_reddit_rss
import aiohttp
import ssl
import certifi

logger = logging.getLogger(__name__)

_ssl_context = ssl.create_default_context(cafile=certifi.where())


def execute_exa_search_news(exa: Exa, query: str, num_results: int = 10) -> str:
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = exa.search_and_contents(
            query,
            category="news",
            type="auto",
            num_results=num_results,
            start_published_date=start_date,
            highlights={"max_characters": 4000},
        )
        return _format_exa_results(response.results)
    except Exception as e:
        logger.error(f"exa_search_news failed: {e}")
        return json.dumps({"error": str(e), "suggestion": "try a different query or skip"})


def execute_exa_search_tweets(exa: Exa, query: str, num_results: int = 10) -> str:
    try:
        start_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = exa.search_and_contents(
            query,
            category="tweet",
            type="auto",
            num_results=num_results,
            start_published_date=start_date,
            highlights={"max_characters": 2000},
        )
        return _format_exa_results(response.results)
    except Exception as e:
        logger.error(f"exa_search_tweets failed: {e}")
        return json.dumps({"error": str(e), "suggestion": "try a different query or skip"})


def execute_exa_get_contents(exa: Exa, urls: list[str]) -> str:
    try:
        urls = urls[:5]  # Max 5 URLs
        response = exa.get_contents(urls, highlights={"max_characters": 4000})
        return _format_exa_results(response.results)
    except Exception as e:
        logger.error(f"exa_get_contents failed: {e}")
        return json.dumps({"error": str(e), "suggestion": "skip this URL"})


def execute_fetch_reddit_rss(subreddits: list[str], user_agent: str) -> str:
    try:
        async def _fetch():
            connector = aiohttp.TCPConnector(ssl=_ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                all_articles = []
                for sub in subreddits:
                    articles = await _fetch_reddit_rss(session, sub, user_agent)
                    all_articles.extend(articles)
                    if sub != subreddits[-1]:
                        await asyncio.sleep(1)
                return all_articles

        articles = asyncio.run(_fetch())
        items = [
            {
                "title": a.title,
                "url": a.url,
                "content": a.content[:500],
                "source": f"reddit/r/{a.source_name}",
            }
            for a in articles
        ]
        return json.dumps(items, ensure_ascii=False)
    except Exception as e:
        logger.error(f"fetch_reddit_rss failed: {e}")
        return json.dumps({"error": str(e), "suggestion": "skip Reddit or try exa_search_news with Reddit topics"})


def _format_exa_results(results) -> str:
    items = []
    for r in results:
        item = {
            "title": r.title or "",
            "url": r.url or "",
            "highlights": r.highlights if hasattr(r, "highlights") and r.highlights else [],
        }
        if hasattr(r, "published_date") and r.published_date:
            item["published_date"] = r.published_date
        items.append(item)
    return json.dumps(items, ensure_ascii=False)
```

- [ ] **Step 4: Run test — verify PASS**

```bash
pytest tests/test_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/tools.py tests/test_tools.py
git commit -m "feat: add tool implementations for Agent mode (Exa search, Reddit RSS)"
```

---

### Task 3: Agent Module

**Files:**
- Create: `src/agent.py`
- Create: `tests/test_agent.py`

- [ ] **Step 1: Write failing tests for agent**

```python
# tests/test_agent.py
import json
from unittest.mock import MagicMock, patch
from src.agent import run_agent, TOOLS, AGENT_SYSTEM_PROMPT
from src.config import Config


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


def test_tools_defined_correctly():
    assert len(TOOLS) == 4
    names = {t["name"] for t in TOOLS}
    assert names == {"exa_search_news", "exa_search_tweets", "exa_get_contents", "fetch_reddit_rss"}


def test_agent_system_prompt_contains_key_instructions():
    assert "今日概述" in AGENT_SYSTEM_PROMPT
    assert "模型层" in AGENT_SYSTEM_PROMPT
    assert "10 条" in AGENT_SYSTEM_PROMPT
    assert "容错" in AGENT_SYSTEM_PROMPT


@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_single_turn_no_tools(mock_anthropic_cls, mock_exa_cls, tmp_path):
    """Agent returns digest without calling any tools."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # Claude responds with end_turn directly
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "# 今日概述\n\n今天没有重大新闻。"

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [mock_text_block]
    mock_client.messages.create.return_value = mock_response

    config = make_test_config(tmp_path)
    result = run_agent(config)

    assert "今日概述" in result


@patch("src.agent.execute_tool")
@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_with_tool_call(mock_anthropic_cls, mock_exa_cls, mock_execute, tmp_path):
    """Agent calls a tool, then returns digest."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # First response: tool_use
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "tool_1"
    mock_tool_block.name = "exa_search_news"
    mock_tool_block.input = {"query": "AI news"}

    mock_response_1 = MagicMock()
    mock_response_1.stop_reason = "tool_use"
    mock_response_1.content = [mock_tool_block]

    # Second response: end_turn
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = "# 今日概述\n\nAI 领域有突破。"

    mock_response_2 = MagicMock()
    mock_response_2.stop_reason = "end_turn"
    mock_response_2.content = [mock_text_block]

    mock_client.messages.create.side_effect = [mock_response_1, mock_response_2]
    mock_execute.return_value = json.dumps([{"title": "News", "url": "https://example.com"}])

    config = make_test_config(tmp_path)
    result = run_agent(config)

    assert "今日概述" in result
    mock_execute.assert_called_once_with("exa_search_news", {"query": "AI news"}, mock_exa_cls.return_value, config)


@patch("src.agent.execute_tool")
@patch("src.agent.Exa")
@patch("src.agent.anthropic.Anthropic")
def test_agent_respects_max_tool_calls(mock_anthropic_cls, mock_exa_cls, mock_execute, tmp_path):
    """Agent stops calling tools after max_tool_calls."""
    config = make_test_config(tmp_path)
    # Override to a small limit
    config = Config(**{**config.__dict__, "max_tool_calls": 2})

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # Always return tool_use
    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.id = "tool_x"
    mock_tool_block.name = "exa_search_news"
    mock_tool_block.input = {"query": "AI"}

    mock_tool_response = MagicMock()
    mock_tool_response.stop_reason = "tool_use"
    mock_tool_response.content = [mock_tool_block]

    # Final response after forced stop
    mock_text = MagicMock()
    mock_text.type = "text"
    mock_text.text = "# 今日概述\n\n强制结束。"
    mock_end_response = MagicMock()
    mock_end_response.stop_reason = "end_turn"
    mock_end_response.content = [mock_text]

    mock_client.messages.create.side_effect = [
        mock_tool_response, mock_tool_response, mock_end_response
    ]
    mock_execute.return_value = "[]"

    result = run_agent(config)
    assert "强制结束" in result
```

- [ ] **Step 2: Run test — verify FAIL**

```bash
pytest tests/test_agent.py -v
```

- [ ] **Step 3: Implement src/agent.py**

```python
# src/agent.py
import json
import logging
import time

import anthropic
from exa_py import Exa

from src.config import Config
from src.tools import (
    execute_exa_search_news,
    execute_exa_search_tweets,
    execute_exa_get_contents,
    execute_fetch_reddit_rss,
)

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """你是一个 AI 科技新闻 Agent。你的任务是收集今天最重要的 AI 新闻，生成一份精炼的中文日报。

## 工作流程

1. **收集阶段**：使用工具搜索多个来源
   - 用 exa_search_news 搜索今日 AI 重大新闻（建议搜索 2-3 个不同关键词）
   - 用 exa_search_tweets 看看 Twitter 上的 AI 讨论热点
   - 用 fetch_reddit_rss 抓取 Reddit AI 社区的热帖

2. **验证阶段**：如果某条新闻需要更多背景
   - 用 exa_get_contents 获取原文详情
   - 用 exa_search_news 搜索相关报道交叉验证

3. **生成阶段**：整理所有收集到的信息，输出日报

## 容错规则
- 工具调用失败时，不要停止，继续用其他工具或已有信息
- 如果某个来源完全不可用，跳过它，用其他来源补充
- 最终只要有任何有效信息，就生成日报

## 输出格式

### 今日概述
3-5 句话概括今天 AI 领域最重要的动态。

### 模型层
大模型发布、架构创新、训练方法突破等。

### 应用层
AI 产品发布、功能更新、开发者工具等。

### 行业动态
融资、收购、合作、政策法规等。

### 开源与社区
开源项目、社区讨论、数据集发布等。

### 其他值得关注
不属于以上分类但有价值的内容。

## 每条新闻格式
- **中文标题**
- 一句话中文摘要
- 原文链接

## 注意
- 总量严格控制在 10 条以内
- 所有标题和摘要必须是中文
- 如果某个分类没有内容，跳过该分类
- 优先选择：重大发布 > 技术突破 > 行业趋势 > 社区讨论
"""

TOOLS = [
    {
        "name": "exa_search_news",
        "description": "搜索最近24小时的AI科技新闻。返回标题、URL和摘要。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "num_results": {"type": "integer", "description": "返回结果数量，默认10", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "exa_search_tweets",
        "description": "搜索Twitter/X上的AI相关讨论和公告。返回推文内容和URL。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "num_results": {"type": "integer", "description": "返回结果数量，默认10", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "exa_get_contents",
        "description": "获取指定URL的网页内容，用于补充新闻背景。最多5个URL。",
        "input_schema": {
            "type": "object",
            "properties": {
                "urls": {"type": "array", "items": {"type": "string"}, "description": "URL列表"},
            },
            "required": ["urls"],
        },
    },
    {
        "name": "fetch_reddit_rss",
        "description": "抓取指定Reddit subreddit的热门帖子。返回标题、内容摘要和URL。",
        "input_schema": {
            "type": "object",
            "properties": {
                "subreddits": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "subreddit列表，如 ['MachineLearning', 'LocalLLaMA']",
                },
            },
            "required": ["subreddits"],
        },
    },
]


def execute_tool(name: str, tool_input: dict, exa: Exa, config: Config) -> str:
    logger.info(f"Executing tool: {name} with input: {json.dumps(tool_input, ensure_ascii=False)[:200]}")

    if name == "exa_search_news":
        return execute_exa_search_news(
            exa, tool_input["query"], tool_input.get("num_results", config.exa_default_num_results)
        )
    elif name == "exa_search_tweets":
        return execute_exa_search_tweets(
            exa, tool_input["query"], tool_input.get("num_results", config.exa_default_num_results)
        )
    elif name == "exa_get_contents":
        return execute_exa_get_contents(exa, tool_input["urls"])
    elif name == "fetch_reddit_rss":
        return execute_fetch_reddit_rss(
            tool_input["subreddits"], config.reddit_user_agent
        )
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent(config: Config) -> str:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    exa = Exa(api_key=config.exa_api_key)

    messages = [{"role": "user", "content": "请生成今天的 AI 日报。"}]
    tool_call_count = 0
    start_time = time.time()

    while True:
        # Safety: max tool calls
        if tool_call_count >= config.max_tool_calls:
            logger.warning(f"Max tool calls ({config.max_tool_calls}) reached, forcing completion")
            messages.append({
                "role": "user",
                "content": "已达到最大工具调用次数，请用已收集的信息立即生成日报。不要再调用工具。",
            })

        # Safety: max runtime
        elapsed = time.time() - start_time
        if elapsed > config.max_runtime_seconds:
            logger.warning(f"Max runtime ({config.max_runtime_seconds}s) exceeded, forcing completion")
            messages.append({
                "role": "user",
                "content": "已超时，请立即用已收集的信息生成日报。不要再调用工具。",
            })

        response = client.messages.create(
            model=config.claude_model,
            max_tokens=config.max_tokens,
            system=AGENT_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            # Preserve full response (text + tool_use blocks)
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool_use block
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_call_count += 1
                    result = execute_tool(block.name, block.input, exa, config)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            digest = "\n".join(text_parts)
            logger.info(f"Agent completed: {tool_call_count} tool calls in {time.time() - start_time:.1f}s")
            return digest

        else:
            logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_parts) if text_parts else ""
```

- [ ] **Step 4: Run test — verify PASS**

```bash
pytest tests/test_agent.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/agent.py tests/test_agent.py
git commit -m "feat: add Agent module with tool_use loop and safety limits"
```

---

### Task 4: Update Main Pipeline + Fetcher Cleanup

**Files:**
- Modify: `src/main.py`
- Modify: `src/fetcher.py`
- Modify: `tests/test_fetcher.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Update src/fetcher.py — remove Twitter/RSSHub code**

Remove `fetch_twitter_rss` and `fetch_all`. Keep only `fetch_reddit_rss` and `_parse_feed`. Remove RSSHub instance fallback logic.

- [ ] **Step 2: Update tests/test_fetcher.py — remove Twitter tests**

Remove `test_fetch_twitter_rss_parses_articles`, `test_fetch_twitter_rss_fallback_on_failure`, `test_fetch_twitter_rss_returns_empty_on_malformed_xml`. Keep Reddit tests and `test_fetch_reddit_rss_returns_empty_on_empty_feed`.

- [ ] **Step 3: Update src/main.py — replace old pipeline with Agent**

```python
# src/main.py
import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_config, Config
from src.database import Database
from src.email_sender import generate_subject, render_email, send_email
from src.agent import run_agent

logger = logging.getLogger(__name__)


def run_pipeline(config: Config) -> None:
    db = Database(config.db_path)
    db.init()

    try:
        # Step 1: Retry unsent digests
        try:
            _retry_unsent_digests(db, config)
        except Exception as e:
            logger.error(f"Retry unsent digests failed: {e}", exc_info=True)

        # Step 2: Run Agent to collect news and generate digest
        logger.info("Running Agent to generate digest...")
        try:
            summary_md = run_agent(config)
        except Exception as e:
            logger.error(f"Agent failed: {e}, falling back to empty digest", exc_info=True)
            summary_md = ""

        if not summary_md.strip():
            logger.info("Agent produced no content, skipping digest")
            db.cleanup(config.cleanup_days)
            return

        # Step 3: Render
        html_content = render_email(summary_md)
        subject = generate_subject(date.today(), _extract_highlight(summary_md))
        digest_id = db.save_digest(subject, html_content)

        # Step 4: Send
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

        # Step 5: Mark + Cleanup
        db.mark_digest_sent(digest_id)
        logger.info("Digest sent successfully")
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

    trigger = CronTrigger.from_crontab(config.schedule_cron, timezone=config.timezone)

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

- [ ] **Step 4: Update tests/test_pipeline.py**

```python
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
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/fetcher.py tests/test_fetcher.py tests/test_pipeline.py
git commit -m "refactor: replace old pipeline with Agent mode, clean up Twitter code"
```

---

### Task 5: Full Test Suite + Integration Test

- [ ] **Step 1: Run full test suite and fix any failures**

```bash
pytest tests/ -v --tb=short
```

- [ ] **Step 2: Run a real integration test**

```bash
source venv/bin/activate && python -c "
from src.config import load_config
from src.main import run_pipeline
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
config = load_config()
from src.database import Database
db = Database(config.db_path)
db.init()
db._execute('DELETE FROM articles')
db._execute('DELETE FROM digests')
db.close()
run_pipeline(config)
"
```

- [ ] **Step 3: Commit any fixes**

```bash
git add -A && git commit -m "feat: Agent mode upgrade complete — Exa search + Claude tool_use"
```
