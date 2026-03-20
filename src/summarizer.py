# src/summarizer.py
import json
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import Article

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "你是一个资深 AI 科技新闻编辑，服务于 AI 从业者。"
    "你擅长从海量信息中精准识别高价值内容，生成结构清晰、信息密度高的中文日报。"
    "所有输出必须使用中文，包括标题。"
)

USER_PROMPT_TEMPLATE = """请根据以下今日新闻，严格筛选后生成一份精炼的中文 AI 日报。

## 筛选标准（按优先级从高到低）

**必选（出现即入选）：**
- 主流 AI 公司（OpenAI、Anthropic、Google、Meta、Mistral 等）的新模型发布或重大产品更新
- 开源模型发布（新权重、新架构）
- 重大融资、收购、合作
- 影响行业的政策法规

**优先选择：**
- 技术突破：新架构、新训练方法、benchmark 刷新
- 重要工具/框架发布或重大更新
- 有数据支撑的行业趋势分析

**过滤掉：**
- 纯讨论帖、提问帖、个人观点（无新信息量）
- 教程、入门指南、"如何使用 X"类内容
- 重复话题（同一事件只保留信息量最大的一条）
- meme、段子、吐槽

## 输出格式

### 今日概述
3-5 句话，概括今天 AI 领域最值得关注的动态。

### 模型层
大模型发布、架构创新、训练方法突破、benchmark 结果等。

### 应用层
AI 产品发布、功能更新、开发者工具、API 变化等。

### 行业动态
融资、收购、合作、人事变动、政策法规等。

### 开源与社区
开源项目发布、社区重要讨论、数据集发布等。

### 其他值得关注
不属于以上分类但有价值的内容。

## 每条新闻格式
- **中文标题**（将英文翻译为简洁的中文）
- 一句话中文摘要，点明核心信息
- 原文链接

## 注意
- 总量严格控制在 10 条以内，宁缺毋滥
- 如果某个分类没有符合条件的新闻，跳过该分类
- 所有标题和摘要必须是中文

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
    return USER_PROMPT_TEMPLATE.format(
        articles_json=json.dumps(items, ensure_ascii=False, indent=2),
    )


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
    batches: list[list[Article]] = []
    current_batch: list[Article] = []
    current_chars = 0

    for article in articles:
        article_chars = (
            len(article.title)
            + len(_truncate_content(article.content))
            + len(article.url)
            + 100
        )
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
        logger.info(
            f"Splitting {len(articles)} articles into {len(batches)} batches",
        )
        batch_summaries = []
        for i, batch in enumerate(batches):
            prompt = _build_prompt(batch)
            summary = _call_claude(client, model, max_tokens, prompt)
            batch_summaries.append(summary)
            logger.info(f"Batch {i + 1}/{len(batches)} summarized")

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
    logger.info(
        f"Claude API usage: {message.usage.input_tokens} input, "
        f"{message.usage.output_tokens} output tokens",
    )
    return result
