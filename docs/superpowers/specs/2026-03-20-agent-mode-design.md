# Agent Mode Upgrade — Design Spec

## Overview

将现有的"RSS 抓取 → 一次性 Claude 总结"流程升级为 Agent 主流程。Claude 作为 Agent，通过 tool_use 自主调用搜索和抓取工具，主动搜索、筛选、验证新闻，生成更高质量的 AI 日报。

## 为什么升级

现有问题：
1. RSSHub 公共实例无法抓取 Twitter/X
2. 信息来源仅限 RSS，无法补充背景
3. Claude 只做一次性总结，无法主动探索

升级后：
1. Exa 搜索覆盖 Twitter、新闻、论文
2. Claude 可主动搜索补充信息
3. 工具失败不中断流程，Agent 自行处理

## Architecture

```
APScheduler 每日触发
       ↓
  Agent 主流程（Claude tool_use 循环）
       │
       ├── Tool: exa_search_news    → Exa API 搜索 AI 新闻
       ├── Tool: exa_search_tweets  → Exa API 搜索 Twitter AI 讨论
       ├── Tool: exa_get_contents   → Exa API 获取文章详情
       ├── Tool: fetch_reddit_rss   → Reddit RSS 抓取
       │
       ↓
  Claude 自主推理循环：
    1. 调用工具收集信息
    2. 分析、筛选、交叉验证
    3. 需要更多信息时继续调用工具
    4. 信息充足时输出最终日报
       ↓
  渲染 HTML → 存入 digests → 发送邮件
```

## Agent 工具定义

### Tool 1: exa_search_news

搜索最近 24 小时的 AI 科技新闻。

```python
{
    "name": "exa_search_news",
    "description": "搜索最近24小时的AI科技新闻。返回标题、URL和摘要。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如 'AI model release', 'OpenAI announcement'"
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数量，默认10",
                "default": 10
            }
        },
        "required": ["query"]
    }
}
```

实现：调用 `exa.search_and_contents(query, category="news", type="auto", num_results=N, highlights={"max_characters": 4000})`，过滤最近 24 小时。

### Tool 2: exa_search_tweets

搜索 Twitter/X 上的 AI 相关讨论。

```python
{
    "name": "exa_search_tweets",
    "description": "搜索Twitter/X上的AI相关讨论和公告。返回推文内容和URL。",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "搜索关键词，如 'GPT-5', 'Claude new model'"
            },
            "num_results": {
                "type": "integer",
                "description": "返回结果数量，默认10",
                "default": 10
            }
        },
        "required": ["query"]
    }
}
```

实现：调用 `exa.search_and_contents(query, category="tweet", type="auto", num_results=N, highlights={"max_characters": 2000})`

### Tool 3: exa_get_contents

获取指定 URL 的详细内容，用于补充背景信息。

```python
{
    "name": "exa_get_contents",
    "description": "获取指定URL的网页内容，用于补充新闻背景。",
    "input_schema": {
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要获取内容的URL列表，最多5个"
            }
        },
        "required": ["urls"]
    }
}
```

实现：调用 `exa.get_contents(urls, highlights={"max_characters": 4000})`

### Tool 4: fetch_reddit_rss

抓取 Reddit subreddit 的热帖。

```python
{
    "name": "fetch_reddit_rss",
    "description": "抓取指定Reddit subreddit的热门帖子。返回标题、内容摘要和URL。",
    "input_schema": {
        "type": "object",
        "properties": {
            "subreddits": {
                "type": "array",
                "items": {"type": "string"},
                "description": "subreddit列表，如 ['MachineLearning', 'LocalLLaMA']"
            }
        },
        "required": ["subreddits"]
    }
}
```

实现：复用现有 `fetcher.py` 的 Reddit RSS 抓取逻辑。

## Agent 循环流程

```python
def run_agent(config) -> str:
    client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    # system prompt 仅通过 system 参数传入，不放在 messages 中
    messages = [{"role": "user", "content": "请生成今天的 AI 日报。"}]
    tool_call_count = 0
    start_time = time.time()

    while True:
        # 安全限制检查
        if tool_call_count >= config.max_tool_calls:
            # 强制结束：追加指令让 Claude 用已有信息生成日报
            messages.append({
                "role": "user",
                "content": "已达到最大工具调用次数，请用已收集的信息生成日报。"
            })
        if time.time() - start_time > config.max_runtime_seconds:
            messages.append({
                "role": "user",
                "content": "已超时，请立即用已收集的信息生成日报。"
            })

        response = client.messages.create(
            model=config.claude_model,
            max_tokens=8192,  # Agent 模式需要更多 token
            system=AGENT_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            # response.content 可能包含混合块（TextBlock + ToolUseBlock）
            # 必须保留所有块，包括 Claude 的中间推理文本
            messages.append({"role": "assistant", "content": response.content})

            # 执行所有 tool_use 块，收集结果
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_call_count += 1
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # 必须匹配 ToolUseBlock 的 id
                        "content": result,
                    })

            # tool_result 必须以 user 消息发送，每个 tool_use 都要有对应的 result
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # 提取所有 TextBlock 的文本作为最终日报
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_parts)
```

### 关键 API 细节

1. **system prompt 只通过 `system` 参数传入**，不放在 messages 的 user 消息中，避免重复
2. **response.content 是混合块列表**：可能同时包含 TextBlock（推理文本）和 ToolUseBlock（工具调用），必须全部保留
3. **tool_result 必须引用 tool_use_id**：每个 ToolUseBlock 有唯一 id，对应的 tool_result 必须包含相同的 id
4. **一次响应可能包含多个 tool_use**：必须为每个 tool_use 都返回 tool_result
5. **max_tokens 设为 8192**：Agent 模式下 Claude 需要更多输出空间（工具调用 + 最终日报）

## Agent System Prompt

```
你是一个 AI 科技新闻 Agent。你的任务是收集今天最重要的 AI 新闻，生成一份精炼的中文日报。

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
```

## 工具容错策略

每个工具调用都包裹在 try/except 中：

| 场景 | 处理方式 |
|------|---------|
| Exa API 超时/错误 | 返回错误信息给 Claude，Claude 决定重试或跳过 |
| Reddit RSS 失败 | 返回错误信息给 Claude，Claude 用 Exa 搜索 Reddit 内容替代 |
| 单个工具多次失败 | 返回 "该工具暂时不可用" 给 Claude |
| 全部工具失败 | Agent 循环超时，发送"今日无法获取新闻"通知邮件 |

工具返回给 Claude 的错误格式：
```json
{"error": "Exa search failed: rate limited", "suggestion": "try a different query or skip this source"}
```

Claude 收到错误后自行决定下一步行动。

## 安全限制

防止 Agent 无限循环：
- **最大工具调用次数**：15 次（超过则强制结束，用已有信息生成日报）
- **最大运行时间**：5 分钟（超时则强制结束）
- **单次 Exa 搜索结果数**：最多 10 条

## 配置变更

### config.yaml 新增

```yaml
agent:
  max_tool_calls: 15
  max_runtime_seconds: 300

exa:
  default_num_results: 10
```

### .env 新增

```
EXA_API_KEY=your-exa-api-key
```

### .env.example 更新

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
EXA_API_KEY=your-exa-api-key
```

### requirements.txt 新增

```
exa-py>=2.0
```

### config.yaml 变更

- 移除 `sources.twitter` 节（RSSHub 不可用，Twitter 来源改由 Exa 搜索）
- 保留 `sources.reddit` 节
- 新增 `agent` 和 `exa` 节

### Config 类变更

- 新增字段：`exa_api_key: str`、`max_tool_calls: int`、`max_runtime_seconds: int`、`exa_default_num_results: int`
- `exa_api_key` 加入 `load_config()` 的 required_env 校验（缺失时启动报错）
- 移除 `rsshub_instances`、`twitter_accounts` 字段

## 受影响的文件

| 文件 | 变更 |
|------|------|
| `src/config.py` | Config 新增 exa_api_key, max_tool_calls, max_runtime_seconds；移除 rsshub/twitter 字段 |
| `src/agent.py` | **新建** — Agent 循环、工具定义、工具执行、安全限制 |
| `src/tools.py` | **新建** — 工具实现（exa_search, exa_contents, fetch_reddit 封装），含数据库去重 |
| `src/summarizer.py` | 保留不动，作为降级备份 |
| `src/main.py` | run_pipeline 改为调用 agent，异常时降级到 summarizer |
| `src/fetcher.py` | 移除 fetch_twitter_rss 和 RSSHub 相关代码，保留 Reddit |
| `config.yaml` | 移除 twitter 节，新增 agent 和 exa 节 |
| `.env.example` | 新增 EXA_API_KEY |
| `requirements.txt` | 新增 exa-py |
| `tests/test_agent.py` | **新建** — Agent 流程测试（mock tool_use 响应） |
| `tests/test_tools.py` | **新建** — 工具单元测试（mock Exa/RSS） |
| `tests/test_config.py` | 更新：适配新 Config 字段 |
| `tests/test_fetcher.py` | 更新：移除 Twitter 相关测试 |

## Pipeline 变更

### 之前
```
Retry → Fetch(RSS) → Process(去重) → Summarize(一次性Claude) → Render → Send → Cleanup
```

### 之后
```
Retry → Agent(Claude循环调用工具收集+生成日报) → Render → Send → Mark → Cleanup
```

### 去重策略

保留数据库去重层：
- 每个工具返回结果前，通过 `database.article_exists(url_hash)` 检查是否已发送过
- 工具返回的结果会标注 `[已发送]`，Claude 可自行跳过
- 跨来源去重（同一新闻在 Exa news 和 Reddit 都出现）由 Claude 在推理中处理
- 最终入选的新闻 URL 存入 articles 表，标记 sent_at

### 降级策略

Agent 模式是主流程，但在以下情况自动降级：
- **Anthropic API 不可用**：捕获 API 异常，回退到旧流程（RSS + 一次性总结使用 summarizer.py）
- **EXA_API_KEY 未配置**：启动时检测，打印警告，Agent 仅使用 fetch_reddit_rss 工具
- **Agent 循环异常退出**：捕获异常，回退到旧流程

## 日报生成对比

| 维度 | 之前 | 之后 |
|------|------|------|
| 信息来源 | Reddit RSS only | Reddit RSS + Exa 新闻 + Twitter + 论文 |
| Twitter 覆盖 | 无（RSSHub 不可用） | Exa tweet 搜索 |
| 信息验证 | 无 | Claude 可交叉搜索验证 |
| 内容补充 | 无 | Claude 可主动获取原文 |
| 筛选方式 | Prompt 指令 | Agent 多步推理 |
| Claude API 调用 | 1 次 | 3-8 次（工具调用 + 最终输出） |
| 成本 | 低 | 中等（更多 API 调用，但质量更高） |
