# src/main.py
import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import asyncio

import anthropic

from src.config import load_config, Config
from src.database import Database
from src.email_sender import generate_subject, render_email, send_email
from src.agent import run_agent
from src.fetcher import fetch_reddit_rss
from src.processor import process_articles
from src.summarizer import summarize_articles

logger = logging.getLogger(__name__)


def run_pipeline(config: Config) -> None:
    db = Database(config.db_path)
    db.init()

    try:
        # Step 1: Retry unsent digests
        try:
            _retry_unsent_digests(db, config)
        except Exception as e:
            logger.error(f"Retry unsent digests failed: {e}", exc_info=True)

        # Step 2: Run Agent (with fallback to old summarizer)
        logger.info("Running Agent to generate digest...")
        try:
            summary_md = run_agent(config)
        except Exception as e:
            logger.error(f"Agent failed: {e}, falling back to old pipeline", exc_info=True)
            summary_md = _fallback_summarize(config, db)

        if not summary_md or not summary_md.strip():
            logger.info("No content produced, skipping digest")
            db.cleanup(config.cleanup_days)
            return

        # Step 3: Render
        html_content = render_email(summary_md)
        subject = generate_subject(date.today(), _extract_highlight(summary_md))
        digest_id = db.save_digest(subject, html_content)

        # Step 4: Send
        logger.info(f"Sending digest to {len(config.recipients)} recipients...")
        send_email(
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            sender=config.gmail_address,
            password=config.gmail_password,
            recipients=config.recipients,
            subject=subject,
            html_content=html_content,
        )

        # Step 5: Mark + Cleanup
        db.mark_digest_sent(digest_id)
        logger.info("Digest sent successfully")
        db.cleanup(config.cleanup_days)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
    finally:
        db.close()


def _retry_unsent_digests(db: Database, config: Config) -> None:
    unsent = db.get_unsent_digests()
    for digest in unsent:
        logger.info(f"Retrying unsent digest {digest['id']}: {digest['subject']}")
        try:
            send_email(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                sender=config.gmail_address,
                password=config.gmail_password,
                recipients=config.recipients,
                subject=digest["subject"],
                html_content=digest["html_content"],
            )
            db.mark_digest_sent(digest["id"])
            logger.info(f"Unsent digest {digest['id']} sent successfully")
        except Exception as e:
            logger.error(f"Retry failed for digest {digest['id']}: {e}")


def _fallback_summarize(config: Config, db: Database) -> str:
    """Fallback: use old RSS + one-shot Claude summarize when Agent fails."""
    logger.info("Fallback: fetching Reddit RSS and summarizing directly...")
    try:
        import aiohttp
        import ssl
        import certifi

        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

        async def _fetch():
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                all_articles = []
                for sub in config.reddit_subreddits:
                    articles = await fetch_reddit_rss(session, sub, config.reddit_user_agent)
                    all_articles.extend(articles)
                    await asyncio.sleep(1)
                return all_articles

        articles = asyncio.run(_fetch())
        new_articles = process_articles(articles, db)

        if not new_articles:
            return ""

        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        return summarize_articles(new_articles, client, config.claude_model, config.max_tokens)
    except Exception as e:
        logger.error(f"Fallback also failed: {e}", exc_info=True)
        return ""


def _extract_highlight(markdown_text: str) -> str:
    lines = markdown_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:50]
    return ""


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    logger.info("AI RSS Email Agent started")

    trigger = CronTrigger.from_crontab(config.schedule_cron, timezone=config.timezone)

    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, trigger, args=[config], id="daily_digest")

    logger.info(f"Scheduled daily digest: {config.schedule_cron} ({config.timezone})")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
