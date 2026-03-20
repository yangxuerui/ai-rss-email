# src/models.py
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib


@dataclass(frozen=True)
class Article:
    url: str
    url_hash: str
    title: str
    content: str
    source: str
    source_name: str
    published_at: datetime
    fetched_at: datetime


def create_article(
    url: str,
    title: str,
    content: str,
    source: str,
    source_name: str,
    published_at: datetime,
) -> Article:
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return Article(
        url=url,
        url_hash=url_hash,
        title=title,
        content=content,
        source=source,
        source_name=source_name,
        published_at=published_at,
        fetched_at=datetime.now(timezone.utc),
    )
