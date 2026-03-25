# tests/test_email_sender.py
from unittest.mock import patch, MagicMock
from src.email_sender import render_email, send_email, generate_subject
from datetime import date


def test_render_email_produces_html():
    markdown_content = "# 今日概述\n\nAI 领域有重大突破。\n\n- **标题1** 摘要"
    html = render_email(markdown_content)
    assert "<h1>" in html or "<h1" in html
    assert "今日概述" in html
    assert "<!DOCTYPE html>" in html


def test_generate_subject():
    subject = generate_subject(date(2026, 3, 20), "GPT-5发布, Claude更新")
    assert "AI 日报" in subject
    assert "2026-03-20" in subject


def test_send_email_calls_smtp_starttls():
    with patch("src.email_sender.smtplib.SMTP") as mock_smtp_class:
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        send_email(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            sender="test@gmail.com",
            password="password",
            recipients=["a@test.com"],
            subject="Test",
            html_content="<h1>Hello</h1>",
        )

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once()
        mock_smtp.send_message.assert_called_once()


def test_send_email_calls_smtp_ssl():
    with patch("src.email_sender.smtplib.SMTP_SSL") as mock_smtp_ssl_class:
        mock_smtp = MagicMock()
        mock_smtp_ssl_class.return_value = mock_smtp
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)

        send_email(
            smtp_host="smtp.163.com",
            smtp_port=465,
            sender="test@163.com",
            password="password",
            recipients=["a@test.com", "b@test.com"],
            subject="Test",
            html_content="<h1>Hello</h1>",
        )

        mock_smtp.login.assert_called_once()
        assert mock_smtp.send_message.call_count == 2
