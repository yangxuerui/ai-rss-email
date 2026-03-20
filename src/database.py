# src/database.py
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from src.models import Article


class Database:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self._get_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor

    def init(self) -> None:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        self._execute("""
            CREATE TABLE IF NOT EXISTS articles (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                title TEXT,
                content TEXT,
                source TEXT,
                source_name TEXT,
                published_at TIMESTAMP,
                fetched_at TIMESTAMP,
                sent_at TIMESTAMP
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP NOT NULL,
                subject TEXT NOT NULL,
                html_content TEXT NOT NULL,
                sent_at TIMESTAMP
            )
        """)

    def insert_article(self, article: Article) -> None:
        self._execute(
            """INSERT OR IGNORE INTO articles
               (url_hash, url, title, content, source, source_name, published_at, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (article.url_hash, article.url, article.title, article.content,
             article.source, article.source_name, article.published_at, article.fetched_at),
        )

    def article_exists(self, url_hash: str) -> bool:
        cursor = self._execute(
            "SELECT 1 FROM articles WHERE url_hash = ?", (url_hash,)
        )
        return cursor.fetchone() is not None

    def get_unsent_articles(self) -> list[Article]:
        cursor = self._execute(
            "SELECT * FROM articles WHERE sent_at IS NULL ORDER BY published_at DESC"
        )
        return [
            Article(
                url=row["url"], url_hash=row["url_hash"], title=row["title"],
                content=row["content"], source=row["source"],
                source_name=row["source_name"],
                published_at=row["published_at"], fetched_at=row["fetched_at"],
            )
            for row in cursor.fetchall()
        ]

    def mark_articles_sent(self, url_hashes: list[str]) -> None:
        now = datetime.now(timezone.utc)
        for h in url_hashes:
            self._execute(
                "UPDATE articles SET sent_at = ? WHERE url_hash = ?", (now, h)
            )

    def save_digest(self, subject: str, html_content: str) -> int:
        cursor = self._execute(
            "INSERT INTO digests (created_at, subject, html_content) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc), subject, html_content),
        )
        return cursor.lastrowid

    def get_unsent_digests(self) -> list[dict]:
        cursor = self._execute(
            "SELECT id, subject, html_content, created_at FROM digests WHERE sent_at IS NULL"
        )
        return [dict(row) for row in cursor.fetchall()]

    def mark_digest_sent(self, digest_id: int) -> None:
        self._execute(
            "UPDATE digests SET sent_at = ? WHERE id = ?",
            (datetime.now(timezone.utc), digest_id),
        )

    def cleanup(self, days: int = 3) -> None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        self._execute(
            "DELETE FROM articles WHERE sent_at IS NOT NULL AND fetched_at < ?",
            (cutoff,),
        )
        self._execute(
            "DELETE FROM digests WHERE sent_at IS NOT NULL AND created_at < ?",
            (cutoff,),
        )

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
