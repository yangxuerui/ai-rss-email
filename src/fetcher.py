# src/fetcher.py
import asyncio
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


async def fetch_twitter_rss(
    session: aiohttp.ClientSession,
    rsshub_instances: list[str],
    account: str,
) -> list[Article]:
    """Fetch RSS feed for a Twitter account via RSSHub instances with fallback."""
    for instance in rsshub_instances:
        url = f"{instance.rstrip('/')}/twitter/user/{account}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    logger.warning(
                        "RSSHub %s returned %d for %s", instance, resp.status, account
                    )
                    continue
                text = await resp.text()
                return _parse_feed(text, source="twitter", source_name=account)
        except Exception as e:
            logger.warning("RSSHub %s failed for %s: %s", instance, account, e)
            continue

    logger.error("All RSSHub instances failed for %s", account)
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


async def fetch_all(
    rsshub_instances: list[str],
    twitter_accounts: list[str],
    reddit_subreddits: list[str],
    reddit_user_agent: str,
) -> list[Article]:
    """Fetch all configured RSS feeds. Twitter concurrently, Reddit sequentially."""
    articles: list[Article] = []

    connector = aiohttp.TCPConnector(ssl=_ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        # Twitter: concurrent fetching
        twitter_tasks = [
            fetch_twitter_rss(session, rsshub_instances, account)
            for account in twitter_accounts
        ]
        twitter_results = await asyncio.gather(*twitter_tasks, return_exceptions=True)
        for result in twitter_results:
            if isinstance(result, list):
                articles.extend(result)
            else:
                logger.error("Twitter fetch error: %s", result)

        # Reddit: sequential with 1s delay to respect rate limits
        for subreddit in reddit_subreddits:
            result = await fetch_reddit_rss(session, subreddit, reddit_user_agent)
            articles.extend(result)
            if subreddit != reddit_subreddits[-1]:
                await asyncio.sleep(1)

    logger.info("Fetched %d total articles", len(articles))
    return articles


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
