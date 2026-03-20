# AI RSS Email Daily Digest — Design Spec

## Overview

一个 Python Agent 程序，每日从 X (Twitter) 和 Reddit 的 RSS 源抓取 AI 科技新闻，通过 Claude API 生成中文摘要日报，发送至多个邮箱。部署在阿里云服务器上，以 systemd 守护进程运行。

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 ai-rss-email                     │
│                                                  │
│  config.yaml ← 来源/邮箱/调度配置                  │
│       │                                          │
│       ▼                                          │
│  ┌──────────┐    ┌──────────┐    ┌────────────┐ │
│  │ Fetcher  │───▶│ Processor│───▶│ Summarizer │ │
│  │ (RSS)    │    │ (去重/   │    │ (Claude    │ │
│  │          │    │  过滤)   │    │  API)      │ │
│  └──────────┘    └──────────┘    └─────┬──────┘ │
│                                        │        │
│                                        ▼        │
│  ┌──────────┐    ┌──────────────────────┐       │
│  │ SQLite   │◄──▶│ EmailSender (SMTP)   │       │
│  │ (去重DB) │    │ → 多收件人            │       │
│  └──────────┘    └──────────────────────┘       │
│                                                  │
│  APScheduler ── 每日定时触发整个流程               │
│  systemd ── 守护进程管理                          │
└─────────────────────────────────────────────────┘
```

### Modules

| Module | Responsibility |
|--------|---------------|
| **Fetcher** | 从 RSSHub/Reddit RSS 拉取 feed，解析为统一 Article 数据结构 |
| **Processor** | 基于 SQLite 去重（URL hash），过滤 24h 外旧内容，清理 3 天前已发送记录 |
| **Summarizer** | 将当天文章批量发给 Claude API，生成分类概述 + 逐条摘要 |
| **EmailSender** | 渲染 HTML 邮件模板，通过 Gmail SMTP 发送到多个收件人 |
| **Scheduler** | APScheduler 定时触发，默认每天早 8 点（Asia/Shanghai） |
| **Config** | YAML 配置文件 + .env 环境变量（敏感信息仅在 .env 中） |

## Configuration

### config.yaml

```yaml
sources:
  twitter:
    # RSSHub 实例（替代已停运的 Nitter）
    # 可自建 RSSHub 或使用公共实例
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
    # Reddit 要求 User-Agent，否则会 429
    user_agent: "ai-rss-email/1.0"

email:
  smtp_host: "smtp.gmail.com"
  smtp_port: 587
  recipients:
    - "user1@gmail.com"
    - "user2@example.com"

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

### Environment Variables (.env)

敏感信息仅存放于 .env，不在 config.yaml 中引用：

```
ANTHROPIC_API_KEY=sk-ant-...
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

`config.py` 分别加载 YAML（结构配置）和 .env（敏感凭据），合并为统一的 Config 对象。

## Data Model

### Article

```python
@dataclass(frozen=True)
class Article:
    url: str
    url_hash: str       # SHA256(url)
    title: str
    content: str
    source: str         # "twitter" | "reddit"
    source_name: str    # account/subreddit name
    published_at: datetime
    fetched_at: datetime
```

### SQLite Schema

```sql
CREATE TABLE articles (
    url_hash TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    source TEXT,
    source_name TEXT,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP,
    sent_at TIMESTAMP
);

-- 缓存已生成的日报，用于发送失败时重试
CREATE TABLE digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL,
    subject TEXT NOT NULL,
    html_content TEXT NOT NULL,
    sent_at TIMESTAMP           -- NULL 表示未成功发送
);
```

### Data Cleanup

每次运行时，**发送成功后**清理已发送的旧记录（防止清理后崩溃导致数据丢失）：

```sql
DELETE FROM articles WHERE sent_at IS NOT NULL AND fetched_at < datetime('now', '-3 days');
DELETE FROM digests WHERE sent_at IS NOT NULL AND created_at < datetime('now', '-3 days');
```

## Daily Execution Flow

```
1. Retry     → 检查 digests 表中 sent_at 为空的记录，重新发送（无需再调 Claude）
2. Fetch     → 并发拉取所有 RSS 源（asyncio + aiohttp）
3. Process   → 去重（url_hash 查 SQLite）、过滤 24h 内新文章
4. Summarize → 新文章发送给 Claude API，生成日报
5. Render    → 生成 HTML 邮件，存入 digests 表
6. Send      → 发送至所有收件人
7. Mark      → 更新 articles.sent_at 和 digests.sent_at
8. Cleanup   → 删除 3 天前已发送的旧记录
```

## Fetcher Details

- **Twitter RSS via RSSHub**: `https://{rsshub_instance}/twitter/user/{account}`
  - RSSHub 支持自建部署，公共实例也可用
  - 多实例自动 fallback：第一个失败则尝试下一个
- **Reddit RSS**: `https://www.reddit.com/r/{subreddit}/hot.rss`
  - 必须设置 `User-Agent` header，否则 Reddit 返回 429
  - Reddit 源**顺序抓取**（非并发），每个请求间隔 1 秒，避免触发限流
  - Twitter 源可并发抓取
- 使用 `feedparser` 解析 RSS XML
- 使用 `asyncio` + `aiohttp` 进行网络请求
- 使用 `tenacity` 库实现重试（指数退避，最多 2 次）

## Summarizer Details

Claude API Prompt：

```
你是一个 AI 科技新闻编辑。请根据以下今日新闻，生成一份中文 AI 日报：

1. 先写一段 3-5 句的「今日概述」，总结今天最重要的 AI 动态
2. 然后按来源分类，每条新闻给出：
   - 标题
   - 一句话中文摘要
   - 原文链接

新闻列表：
{articles_json}
```

### Token 管理

- 使用 `anthropic` SDK 的 `count_tokens()` 方法精确计算 token 数
- 单批上限：预留 prompt + 输出 token 后，剩余空间用于文章内容
- 若文章总量超过单批上限，按时间排序分批发送
- 每批独立生成摘要，最后一次 Claude 调用将所有批次摘要合并为完整日报
- 单篇文章超长时截断 content 字段（保留前 500 字符）

## Email Details

- Claude 输出 Markdown → `markdown` 库转为 HTML → `jinja2` 模板包裹邮件样式
- 邮件标题：`「AI 日报」2026-03-20 | {今日亮点关键词}`
- 使用 `smtplib` + `email.mime` 发送
- Gmail 需使用 App Password
- 生成的 HTML 内容缓存到 `digests` 表，发送失败可直接重试

## Error Handling

| Scenario | Strategy |
|----------|----------|
| RSSHub 实例不可用 | 自动尝试下一个实例，全部失败则跳过 Twitter 源 |
| Reddit RSS 429/超时 | tenacity 重试 2 次（指数退避），仍失败则跳过该 subreddit |
| Claude API 调用失败 | tenacity 重试 2 次，仍失败则发送未摘要的原始列表（降级模式） |
| Gmail SMTP 发送失败 | 重试 2 次，失败则 digest 保留在表中（sent_at=NULL），下次运行自动补发 |
| 当天无新文章 | 不发送邮件，记录日志 |

## Logging

- Python `logging` 模块，输出到 stdout
- systemd journalctl 自动收集
- 关键事件：抓取数量、去重数量、Claude token 用量、发送结果

## Project Structure

```
ai-rss-email/
├── config.yaml
├── .env
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py            # 入口，初始化 Scheduler
│   ├── config.py          # 加载 YAML + .env，合并为 Config
│   ├── models.py          # Article dataclass
│   ├── fetcher.py         # RSS 抓取（async）
│   ├── processor.py       # 去重、过滤
│   ├── summarizer.py      # Claude API 调用
│   ├── email_sender.py    # 邮件渲染与发送
│   └── database.py        # SQLite 操作（同步，通过 run_in_executor 适配 async）
├── templates/
│   └── email.html         # Jinja2 邮件 HTML 模板
├── data/                  # 运行时生成
│   └── articles.db
├── requirements.txt
├── systemd/
│   └── ai-rss-email.service
└── README.md
```

## Deployment (Alibaba Cloud)

```bash
git clone <repo> /opt/ai-rss-email
cd /opt/ai-rss-email
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with credentials
sudo cp systemd/ai-rss-email.service /etc/systemd/system/
sudo systemctl enable ai-rss-email
sudo systemctl start ai-rss-email
```

### systemd Service

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

## Dependencies

```
feedparser
aiohttp
anthropic
apscheduler>=4.0
tenacity
python-dotenv
pyyaml
jinja2
markdown
```

## Async/Sync 策略

- **主循环**：同步（APScheduler 触发同步函数）
- **Fetcher**：在任务函数内用 `asyncio.run()` 启动异步抓取
- **SQLite**：同步操作，在 async 上下文中通过 `loop.run_in_executor()` 避免阻塞
- **SMTP**：同步（`smtplib`），在 Fetcher 完成后的同步流程中执行

## Tech Decisions

- **RSSHub over Nitter**: Nitter 已于 2024 年停运，RSSHub 是活跃维护的替代方案，支持自建
- **APScheduler over cron**: 进程内调度，便于管理状态和错误处理
- **SQLite over file-based**: 结构化查询、去重高效、无需外部依赖
- **digests 表**: 缓存已生成的邮件内容，发送失败可免费重试（无需再调 Claude）
- **tenacity**: 统一的重试策略，指数退避，避免 ad-hoc 重试逻辑
- **Claude Sonnet + latest alias**: 摘要任务性价比最优，使用 latest alias 自动跟进新版本
- **Frozen dataclass**: 不可变数据结构，防止副作用
- **venv 部署**: 隔离依赖，不污染系统 Python
