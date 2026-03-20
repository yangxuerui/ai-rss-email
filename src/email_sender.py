# src/email_sender.py
import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import markdown
from jinja2 import Template
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "email.html"


def generate_subject(today: date, highlight: str = "") -> str:
    base = f"「AI 日报」{today.isoformat()}"
    if highlight:
        return f"{base} | {highlight}"
    return base


def render_email(markdown_content: str) -> str:
    html_body = markdown.markdown(markdown_content, extensions=["extra", "nl2br"])
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = Template(template_text)
    return template.render(content=html_body)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def send_email(
    smtp_host: str,
    smtp_port: int,
    sender: str,
    password: str,
    recipients: list[str],
    subject: str,
    html_content: str,
) -> None:
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender, password)

        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            server.send_message(msg)
            logger.info(f"Email sent to {recipient}")
