# src/fetcher.py
import logging
import ssl
from datetime import datetime, timezone
from time import mktime

import aiohttp
import certifi
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential

from src.models import Article, create_article

logger = logging.getLogger(__name__)

_ssl_context = ssl.create_default_context(cafile=certifi.where())


async def fetch_rss_feed(
    session: aiohttp.ClientSession,
    url: str,
    source: str,
    source_name: str,
) -> list[Article]:
    """Fetch a generic RSS/Atom feed and return Article objects."""
    try:
        async with session.get(
            url,
            headers={"User-Agent": "ai-rss-email/1.0"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                logger.warning("RSS feed %s returned %d", url, resp.status)
                return []
            text = await resp.text()
            return _parse_feed(text, source=source, source_name=source_name)
    except Exception as e:
        logger.error("RSS fetch failed for %s: %s", url, e)
        return []


async def fetch_reddit_rss(
    session: aiohttp.ClientSession,
    subreddit: str,
    user_agent: str,
) -> list[Article]:
    """Fetch RSS feed for a Reddit subreddit with retry on rate limiting."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
    headers = {"User-Agent": user_agent}
    try:
        return await _fetch_reddit_with_retry(session, url, headers, subreddit)
    except Exception as e:
        logger.error("Reddit fetch failed for r/%s after retries: %s", subreddit, e)
        return []


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def _fetch_reddit_with_retry(
    session: aiohttp.ClientSession,
    url: str,
    headers: dict,
    subreddit: str,
) -> list[Article]:
    """Internal helper: fetch Reddit RSS with tenacity retry on 429."""
    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
        if resp.status == 429:
            raise Exception(f"Reddit rate limited (429) for r/{subreddit}")
        if resp.status != 200:
            logger.warning("Reddit returned %d for r/%s", resp.status, subreddit)
            return []
        text = await resp.text()
        return _parse_feed(text, source="reddit", source_name=subreddit)


def _parse_feed(text: str, source: str, source_name: str) -> list[Article]:
    """Parse RSS/Atom feed text into Article objects."""
    feed = feedparser.parse(text)
    articles: list[Article] = []

    for entry in feed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
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
