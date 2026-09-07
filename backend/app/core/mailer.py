"""Email delivery.

Dev mode logs the OTP instead of sending it, and the API returns it in the
response. That is deliberate: a live demo must never depend on an email
arriving over venue wifi.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("sankhya.mailer")


def send_otp_email(to_email: str, code: str) -> bool:
    subject = "SANKHYA sign-in code"
    body = (
        f"Your SANKHYA sign-in code is {code}\n\n"
        f"It expires in {settings.otp_ttl_seconds // 60} minutes. "
        "If you did not request it, you can ignore this message."
    )

    if not settings.email_enabled:
        log.warning("[DEV MODE] OTP for %s is %s (email sending disabled)", to_email, code)
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_user}>"
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        # Never surface SMTP internals to the caller, and never block sign-in
        # diagnostics on a mail failure.
        log.exception("Failed to send OTP email to %s", to_email)
        return False
