# src/main.py
import asyncio
import logging
from datetime import date

import anthropic
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_config, Config
from src.database import Database
from src.email_sender import generate_subject, render_email, send_email
from src.fetcher import fetch_all
from src.processor import process_articles
from src.summarizer import summarize_articles

logger = logging.getLogger(__name__)


def run_pipeline(config: Config) -> None:
    db = Database(config.db_path)
    db.init()

    try:
        # Step 1: Retry unsent digests
        _retry_unsent_digests(db, config)

        # Step 2: Fetch
        logger.info("Fetching RSS feeds...")
        articles = asyncio.run(
            fetch_all(
                rsshub_instances=config.rsshub_instances,
                twitter_accounts=config.twitter_accounts,
                reddit_subreddits=config.reddit_subreddits,
                reddit_user_agent=config.reddit_user_agent,
            )
        )

        # Step 3: Process
        new_articles = process_articles(articles, db)

        if not new_articles:
            logger.info("No new articles found, skipping digest")
            db.cleanup(config.cleanup_days)
            return

        # Step 4: Summarize
        logger.info(f"Summarizing {len(new_articles)} articles with Claude...")
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        summary_md = summarize_articles(
            new_articles, client, config.claude_model, config.max_tokens
        )

        # Step 5: Render
        html_content = render_email(summary_md)
        subject = generate_subject(date.today(), _extract_highlight(summary_md))
        digest_id = db.save_digest(subject, html_content)

        # Step 6: Send
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

        # Step 7: Mark
        db.mark_articles_sent([a.url_hash for a in new_articles])
        db.mark_digest_sent(digest_id)
        logger.info("Digest sent successfully")

        # Step 8: Cleanup
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

    # Parse cron expression: "0 8 * * *"
    cron_parts = config.schedule_cron.split()
    trigger = CronTrigger(
        minute=cron_parts[0],
        hour=cron_parts[1],
        day=cron_parts[2] if cron_parts[2] != "*" else None,
        month=cron_parts[3] if cron_parts[3] != "*" else None,
        day_of_week=cron_parts[4] if cron_parts[4] != "*" else None,
        timezone=config.timezone,
    )

    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, trigger, args=[config], id="daily_digest")

    logger.info(f"Scheduled daily digest: {config.schedule_cron} ({config.timezone})")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")


if __name__ == "__main__":
    main()
