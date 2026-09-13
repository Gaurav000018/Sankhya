"""Transactional email, delivered through Resend.

Resend rather than SMTP: no long-lived connection to hold open inside a request
handler, no app-password to rotate, and delivery failures come back as a status
code instead of an exception from deep inside `smtplib`.

Two rules hold for every message here:

**Sending never fails a request.** A send returns `bool` and callers treat it as
advisory. If Resend is down, an officer requesting a sign-in code gets the same
neutral response they always do — the alternative leaks account existence
through a 500, and locks people out of a working system because of a mail
outage.

**Dev mode does not send.** With `EMAIL_ENABLED=false` the message is logged and
the code or link is handed back through the API instead, so a demo never waits
on a message arriving over venue wifi. `_require_production_settings` refuses to
boot a production deployment in that state.
"""

from __future__ import annotations

import logging
from html import escape

import httpx

from app.config import settings

log = logging.getLogger("sankhya.mailer")

RESEND_ENDPOINT = "https://api.resend.com/emails"
TIMEOUT_SECONDS = 10.0


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _shell(heading: str, body_html: str, footer: str = "") -> str:
    """One layout for every message.

    Table-based and fully inline-styled because that is what survives Outlook,
    which a government deployment cannot treat as an edge case. Colours are the
    institutional palette, not the product's dark theme: a dark email lands on a
    white background in most clients and looks broken.
    """
    return f"""\
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{escape(heading)}</title></head>
<body style="margin:0;padding:0;background:#f1f3f6;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f1f3f6;padding:32px 12px;">
 <tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="max-width:520px;background:#ffffff;border:1px solid #d8dce3;">
   <tr><td style="padding:22px 28px;border-bottom:1px solid #d8dce3;">
     <span style="font:600 17px/1 Georgia,serif;letter-spacing:.08em;color:#14181f;">SANKHYA</span>
     <span style="font:400 11px/1 Arial,sans-serif;color:#626a7a;padding-left:10px;">
       Ministry of Statistics &amp; Programme Implementation
     </span>
   </td></tr>
   <tr><td style="padding:28px;">
     <h1 style="margin:0 0 14px;font:600 19px/1.3 Georgia,serif;color:#14181f;">{escape(heading)}</h1>
     {body_html}
   </td></tr>
   <tr><td style="padding:16px 28px;border-top:1px solid #d8dce3;
                  font:400 11px/1.6 Arial,sans-serif;color:#626a7a;">
     {footer or "This is an automated message from SANKHYA. Please do not reply."}
   </td></tr>
  </table>
 </td></tr>
</table>
</body></html>"""


def _button(url: str, label: str) -> str:
    # A link styled as a button, never a real <button>: mail clients strip form
    # elements. The raw URL is repeated underneath by every caller, because some
    # clients and most government mail gateways rewrite or strip the anchor.
    return (
        f'<a href="{escape(url, quote=True)}" '
        'style="display:inline-block;background:#182033;color:#ffffff;text-decoration:none;'
        'font:600 14px/1 Arial,sans-serif;padding:13px 22px;border-radius:2px;">'
        f"{escape(label)}</a>"
    )


def _para(text: str) -> str:
    return f'<p style="margin:0 0 14px;font:400 14px/1.65 Arial,sans-serif;color:#4d5563;">{text}</p>'


def _raw_url(url: str) -> str:
    return (
        '<p style="margin:18px 0 0;font:400 12px/1.5 Arial,sans-serif;color:#626a7a;">'
        "If the button does not work, copy this address into your browser:<br>"
        f'<span style="font-family:Consolas,monospace;color:#3d5a9e;word-break:break-all;">'
        f"{escape(url)}</span></p>"
    )


# --------------------------------------------------------------------------- #
# Delivery
# --------------------------------------------------------------------------- #

def _send(to_email: str, subject: str, html: str, text: str) -> bool:
    if not settings.email_enabled:
        # The body is not logged — these carry codes and single-use tokens, and
        # application logs are not a secret store. Callers log what they need.
        log.warning(
            "[DEV MODE] email suppressed: %r to %s (set EMAIL_ENABLED=true to send)",
            subject,
            to_email,
        )
        return True

    if not settings.resend_api_key:
        log.error("EMAIL_ENABLED is true but RESEND_API_KEY is empty; cannot send %r", subject)
        return False

    payload: dict[str, object] = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": subject,
        "html": html,
        # Every message ships a plain-text part. Without one, spam filters score
        # the mail worse and text-only government clients render nothing.
        "text": text,
    }
    if settings.email_reply_to:
        payload["reply_to"] = settings.email_reply_to

    try:
        response = httpx.post(
            RESEND_ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        # Network-level failure. The class name is enough to diagnose; the
        # exception can carry the URL with its key in some configurations.
        log.error("Resend request failed for %s: %s", to_email, type(exc).__name__)
        return False

    if response.status_code >= 400:
        # Resend's error bodies name the cause (unverified domain, invalid key)
        # without echoing the API key back.
        log.error(
            "Resend rejected the message for %s: %s %s",
            to_email,
            response.status_code,
            response.text[:300],
        )
        return False

    log.info("Sent %r to %s", subject, to_email)
    return True


# --------------------------------------------------------------------------- #
# Messages
# --------------------------------------------------------------------------- #

def send_otp_email(to_email: str, code: str) -> bool:
    minutes = settings.otp_ttl_seconds // 60
    html = _shell(
        "Your sign-in code",
        _para("Use this code to sign in to SANKHYA.")
        + '<p style="margin:0 0 14px;font:600 30px/1.2 Consolas,monospace;'
        f'letter-spacing:.22em;color:#14181f;">{escape(code)}</p>'
        + _para(
            f"It expires in {minutes} minutes and can be used once. "
            "If you did not ask for it, you can ignore this message — "
            "no one can sign in without it."
        ),
    )
    text = (
        f"Your SANKHYA sign-in code is {code}\n\n"
        f"It expires in {minutes} minutes and can be used once.\n"
        "If you did not request it, you can ignore this message."
    )
    return _send(to_email, "Your SANKHYA sign-in code", html, text)


def send_verification_email(to_email: str, full_name: str, url: str) -> bool:
    hours = settings.email_token_ttl_hours
    html = _shell(
        "Confirm your email address",
        _para(f"{escape(full_name)}, your SANKHYA account has been created.")
        + _para(
            "Confirm this address to activate it. Until you do, the account "
            "cannot sign in."
        )
        + _button(url, "Confirm this address")
        + _raw_url(url)
        + _para(
            f"<em>The link is valid for {hours} hours.</em> If you did not create "
            "this account, ignore this message and nothing further happens."
        ),
    )
    text = (
        f"{full_name}, your SANKHYA account has been created.\n\n"
        f"Confirm your email address to activate it:\n{url}\n\n"
        f"The link is valid for {hours} hours. If you did not create this "
        "account, you can ignore this message."
    )
    return _send(to_email, "Confirm your SANKHYA account", html, text)


def send_password_reset_email(to_email: str, full_name: str, url: str) -> bool:
    hours = settings.password_reset_ttl_hours
    html = _shell(
        "Reset your password",
        _para(f"{escape(full_name)}, we received a request to reset your SANKHYA password.")
        + _button(url, "Choose a new password")
        + _raw_url(url)
        + _para(
            f"<em>The link is valid for {hours} hours and can be used once.</em> "
            "If you did not request this, ignore the message — your current "
            "password still works and nothing has changed."
        ),
    )
    text = (
        f"{full_name}, we received a request to reset your SANKHYA password.\n\n"
        f"Choose a new password:\n{url}\n\n"
        f"The link is valid for {hours} hours and can be used once. If you did "
        "not request this, your current password still works."
    )
    return _send(to_email, "Reset your SANKHYA password", html, text)


def send_password_changed_email(to_email: str, full_name: str) -> bool:
    """Sent after a successful reset.

    Not a courtesy: this is how someone finds out their account was taken over
    by an attacker who controls the reset link but not the mailbox.
    """
    html = _shell(
        "Your password was changed",
        _para(f"{escape(full_name)}, the password on your SANKHYA account was just changed.")
        + _para(
            "If this was you, nothing further is needed. "
            "<strong>If it was not</strong>, contact your division administrator "
            "immediately — someone else has access to your account."
        ),
    )
    text = (
        f"{full_name}, the password on your SANKHYA account was just changed.\n\n"
        "If this was not you, contact your division administrator immediately."
    )
    return _send(to_email, "Your SANKHYA password was changed", html, text)
