from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.settings import settings


_logger = logging.getLogger(__name__)


_templates_dir = Path(__file__).resolve().parent / "email_templates"
_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(enabled_extensions=("html", "xml")),
)


def _render_template(name: str, context: dict) -> str:
    tpl = _env.get_template(name)
    return tpl.render(**context)


def _smtp_configured() -> bool:
    return bool(settings.smtp_host and (settings.mail_from or settings.smtp_user))


def send_templated_email(*, to: str, subject: str, template_base: str, context: dict) -> None:
    if not to:
        return
    if not _smtp_configured():
        _logger.warning("SMTP not configured; skipping email to %s", to)
        return

    from_addr = settings.mail_from or settings.smtp_user
    if not from_addr:
        _logger.warning("MAIL_FROM not configured; skipping email to %s", to)
        return

    txt_name = f"{template_base}.txt"
    html_name = f"{template_base}.html"

    text_body = _render_template(txt_name, context)
    html_body = None
    try:
        html_body = _render_template(html_name, context)
    except Exception:
        html_body = None

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception:
        _logger.exception("Failed sending email to %s", to)
        raise
