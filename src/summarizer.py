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
