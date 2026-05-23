import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
_raw_port = os.getenv("SMTP_PORT", "").strip()
SMTP_PORT = int(_raw_port) if _raw_port.isdigit() else (465 if _truthy(os.getenv("SMTP_USE_TLS")) else 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Postmarked").strip()
SMTP_USE_TLS = _truthy(os.getenv("SMTP_USE_TLS"))
SMTP_USE_STARTTLS = _truthy(os.getenv("SMTP_USE_STARTTLS", "true"))


def is_email_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM_EMAIL)


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not is_email_configured():
        logger.warning(
            "[email] SMTP is not configured; email not sent to %s with subject %r",
            to_email,
            subject,
        )
        return False

    message = EmailMessage()
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        if SMTP_USE_TLS:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as smtp:
                _send(smtp, message)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                if SMTP_USE_STARTTLS:
                    smtp.starttls(context=ssl.create_default_context())
                _send(smtp, message)
        return True
    except Exception:
        logger.exception("[email] Failed to send email to %s with subject %r", to_email, subject)
        return False


def _send(smtp: smtplib.SMTP, message: EmailMessage) -> None:
    if SMTP_USERNAME:
        smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
    smtp.send_message(message)
