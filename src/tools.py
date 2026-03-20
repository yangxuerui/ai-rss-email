# src/tools.py
import asyncio
import json
import logging
import ssl
from datetime import datetime, timezone, timedelta

import aiohttp
import certifi
from exa_py import Exa

from src.fetcher import fetch_reddit_rss as _fetch_reddit_rss

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
        urls = urls[:5]
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
