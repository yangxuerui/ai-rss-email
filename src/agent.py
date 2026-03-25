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
    execute_fetch_rss_feeds,
)

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """你是一个 AI 科技新闻 Agent。你的任务是收集今天最重要的 AI 新闻，生成一份精炼的中文日报。

## 工作流程

1. **收集阶段**：使用工具搜索多个来源
   - 用 fetch_rss_feeds 抓取所有已配置的 RSS 源（Hacker News、36kr、ArXiv、OpenAI、HuggingFace Papers）
   - 用 fetch_reddit_rss 抓取 Reddit AI 社区的热帖（通过 RSSHub 代理）
   - 用 exa_search_news 搜索今日 AI 重大新闻（建议搜索 2-3 个不同关键词）
   - 用 exa_search_tweets 看看 Twitter 上的 AI 讨论热点

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
        "description": "抓取指定Reddit subreddit的热门帖子（通过RSSHub代理）。返回标题、内容摘要和URL。",
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
    {
        "name": "fetch_rss_feeds",
        "description": "抓取所有已配置的RSS源（Hacker News、36kr快讯、ArXiv AI论文、OpenAI博客、HuggingFace论文精选）。无需参数，自动抓取所有源。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def execute_tool(name: str, tool_input: dict, exa: Exa, config: Config) -> str:
    logger.info(f"Executing tool: {name} with input: {json.dumps(tool_input, ensure_ascii=False)[:200]}")

    if name == "exa_search_news":
        return execute_exa_search_news(exa, tool_input["query"], tool_input.get("num_results", config.exa_default_num_results))
    elif name == "exa_search_tweets":
        return execute_exa_search_tweets(exa, tool_input["query"], tool_input.get("num_results", config.exa_default_num_results))
    elif name == "exa_get_contents":
        return execute_exa_get_contents(exa, tool_input["urls"])
    elif name == "fetch_reddit_rss":
        return execute_fetch_reddit_rss(tool_input["subreddits"], config.reddit_user_agent, config.rsshub_base_url)
    elif name == "fetch_rss_feeds":
        feeds = [{"url": f.url, "source": f.source, "name": f.name} for f in config.rss_feeds]
        return execute_fetch_rss_feeds(feeds)
    else:
        return json.dumps({"error": f"Unknown tool: {name}"})


def run_agent(config: Config) -> str:
    client = anthropic.Anthropic(api_key=config.llm_api_key, base_url=config.llm_base_url)
    exa = Exa(api_key=config.exa_api_key)

    messages = [{"role": "user", "content": "请生成今天的 AI 日报。"}]
    tool_call_count = 0
    start_time = time.time()
    force_stop_sent = False

    while True:
        # Safety: check limits and force stop if needed
        limit_hit = (
            tool_call_count >= config.max_tool_calls
            or (time.time() - start_time) > config.max_runtime_seconds
        )

        if limit_hit and force_stop_sent:
            # Already asked Claude to stop but it's still calling tools — hard exit
            logger.warning("Force stop already sent but Claude still calling tools, extracting text")
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_parts) if text_parts else ""

        if limit_hit and not force_stop_sent:
            logger.warning(f"Safety limit hit (calls={tool_call_count}, elapsed={time.time() - start_time:.0f}s), requesting completion")
            messages.append({
                "role": "user",
                "content": "已达到限制，请用已收集的信息立即生成日报。不要再调用工具。",
            })
            force_stop_sent = True

        response = client.messages.create(
            model=config.llm_model,
            max_tokens=config.max_tokens,
            system=AGENT_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            if force_stop_sent:
                # Claude ignored our stop request — hard exit with any text it produced
                logger.warning("Claude ignored force stop, hard terminating")
                text_parts = [b.text for b in response.content if hasattr(b, "text")]
                return "\n".join(text_parts) if text_parts else ""

            # Preserve full response including text blocks (Claude's reasoning)
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool_use block, collect results
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

            # Send tool results back as user message
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "end_turn":
            # Extract all text blocks as final digest
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            digest = "\n".join(text_parts)
            logger.info(f"Agent completed: {tool_call_count} tool calls in {time.time() - start_time:.1f}s")
            return digest

        else:
            # Unexpected stop reason — extract what we can
            logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            return "\n".join(text_parts) if text_parts else ""
