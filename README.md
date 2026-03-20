# AI RSS Email Daily Digest

一个基于 Claude Agent 模式的 AI 科技新闻日报系统。每天自动从多个来源搜索、筛选、验证 AI 领域最重要的新闻，生成中文日报并发送到邮箱。

## 特性

- **Agent 模式** — Claude 自主调用工具搜索新闻，多步推理筛选，交叉验证
- **多来源覆盖** — Exa 新闻搜索、Twitter/X 讨论、Reddit 社区热帖
- **智能筛选** — 按重要度分类（模型层、应用层、行业动态、开源社区），每日精选 10 条
- **全中文输出** — 标题和摘要自动翻译为中文
- **多邮箱投递** — 支持同时发送到多个收件人
- **容错设计** — 工具失败不中断流程，Agent 异常自动降级到旧管线
- **定时调度** — APScheduler 定时执行，systemd 守护进程管理

## 架构

```
APScheduler 每日触发
       ↓
  Claude Agent（tool_use 循环）
       ├── exa_search_news    → AI 新闻搜索
       ├── exa_search_tweets  → Twitter AI 讨论
       ├── exa_get_contents   → 文章详情获取
       ├── fetch_reddit_rss   → Reddit 社区热帖
       ↓
  Claude 自主推理：搜索 → 筛选 → 验证 → 生成日报
       ↓
  HTML 邮件渲染 → Gmail SMTP 发送
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yangxuerui/ai-rss-email.git
cd ai-rss-email
```

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置

复制环境变量模板并填入真实值：

```bash
cp .env.example .env
```

编辑 `.env`：

```
ANTHROPIC_API_KEY=你的 Anthropic API Key
GMAIL_ADDRESS=你的 Gmail 地址
GMAIL_APP_PASSWORD=Gmail 应用专用密码
EXA_API_KEY=你的 Exa API Key
```

编辑 `config.yaml` 修改收件人邮箱和其他配置。

### 4. 测试运行

```bash
python -c "
from src.config import load_config
from src.main import run_pipeline
import logging
logging.basicConfig(level=logging.INFO)
config = load_config()
run_pipeline(config)
"
```

### 5. 部署（systemd）

```bash
sudo cp systemd/ai-rss-email.service /etc/systemd/system/
sudo systemctl enable ai-rss-email
sudo systemctl start ai-rss-email
```

## 项目结构

```
ai-rss-email/
├── src/
│   ├── agent.py          # Agent 循环 + 工具定义
│   ├── tools.py          # 工具实现（Exa、Reddit）
│   ├── config.py         # 配置加载
│   ├── main.py           # Pipeline 编排 + 调度器
│   ├── email_sender.py   # 邮件渲染与发送
│   ├── database.py       # SQLite 存储
│   ├── fetcher.py        # Reddit RSS 抓取
│   ├── processor.py      # 去重与过滤
│   ├── summarizer.py     # 降级用旧摘要器
│   └── models.py         # Article 数据模型
├── templates/
│   └── email.html        # 邮件 HTML 模板
├── systemd/
│   └── ai-rss-email.service
├── config.yaml           # 来源/邮箱/调度配置
├── .env.example          # 环境变量模板
├── requirements.txt
└── tests/                # 43 个测试
```

## API Keys 获取

| 服务 | 获取地址 | 用途 |
|------|---------|------|
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude API（Agent 推理） |
| Exa | [dashboard.exa.ai](https://dashboard.exa.ai) | 新闻/Twitter 搜索 |
| Gmail | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) | 邮件发送（需开启两步验证） |

## 运行测试

```bash
pytest tests/ -v
```

## License

MIT
