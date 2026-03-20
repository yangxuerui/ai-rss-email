# src/processor.py
import logging
from datetime import datetime, timezone, timedelta

from src.database import Database
from src.models import Article

logger = logging.getLogger(__name__)


def process_articles(
    articles: list[Article],
    db: Database,
    max_age_hours: int = 24,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    new_articles = []

    for article in articles:
        if article.published_at < cutoff:
            continue
        if db.article_exists(article.url_hash):
            continue
        db.insert_article(article)
        new_articles.append(article)

    logger.info(
        f"Processed {len(articles)} articles: "
        f"{len(new_articles)} new, {len(articles) - len(new_articles)} filtered"
    )
    return new_articles
