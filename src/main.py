# src/main.py
import logging
from datetime import date

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import load_config, Config
from src.database import Database
from src.email_sender import generate_subject, render_email, send_email
from src.agent import run_agent

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

        # Step 2: Run Agent
        logger.info("Running Agent to generate digest...")
        try:
            summary_md = run_agent(config)
        except Exception as e:
            logger.error(f"Agent failed: {e}", exc_info=True)
            summary_md = ""

        if not summary_md.strip():
            logger.info("Agent produced no content, skipping digest")
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
