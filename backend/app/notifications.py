import logging
import smtplib
from email.mime.text import MIMEText
from typing import Any

import httpx

from app.config import settings

log = logging.getLogger("avsardoot.notifications")


def send_email(to_addr: str, subject: str, body: str) -> bool:
    if not settings.smtp_host:
        log.info("[NOTIFICATION LOG - EMAIL] To: %s | Subject: %s\nBody: %s", to_addr, subject, body)
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_addr
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception as ex:
        log.error("Failed to send email to %s: %s", to_addr, ex)
        return False


def send_whatsapp(phone_number: str, message: str) -> bool:
    """Delivers WhatsApp Business API message or logs fallback."""
    if not phone_number:
        return False
    # If WhatsApp API configuration is present (e.g. Meta Graph API)
    if hasattr(settings, "whatsapp_api_token") and settings.whatsapp_api_token:
        try:
            url = f"https://graph.facebook.com/v18.0/{settings.whatsapp_phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {settings.whatsapp_api_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": phone_number,
                "type": "text",
                "text": {"body": message},
            }
            resp = httpx.post(url, json=payload, headers=headers, timeout=10)
            return resp.status_code in (200, 201)
        except Exception as ex:
            log.error("WhatsApp API send failed: %s", ex)
            return False

    log.info("[NOTIFICATION LOG - WHATSAPP] To Phone: %s\nMessage:\n%s", phone_number, message)
    return True


def send_telegram(chat_id: str, message: str) -> bool:
    """Send a message via Telegram Bot API. Returns True on success."""
    if not chat_id:
        return False

    if not settings.telegram_bot_token:
        log.info("[NOTIFICATION LOG - TELEGRAM] chat_id=%s\nMessage:\n%s", chat_id, message)
        return True  # Logged OK in dev mode

    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        resp = httpx.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("ok"):
            log.info("Telegram message sent to chat_id=%s", chat_id)
            return True
        log.warning("Telegram API returned non-ok: %s %s", resp.status_code, resp.text)
        return False
    except Exception as ex:
        log.error("Telegram send failed for chat_id=%s: %s", chat_id, ex)
        return False


def match_telegram_message(title: str, reasons: list[str], apply_end: Any, official_url: str, days_left: int | None) -> str:
    """Build a rich HTML Telegram notification message for a new match."""
    why = "; ".join(reasons[:3]) if reasons else "Your profile matches this opportunity"
    deadline_str = str(apply_end) if apply_end else "See official notification"
    if days_left is not None:
        deadline_str += f" ({days_left} days left)"
    return (
        f"<b>🎯 New Match Found!</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"✅ <b>Why you're eligible:</b> {why}\n"
        f"📅 <b>Apply by:</b> {deadline_str}\n"
        f"🔗 <a href=\"{official_url}\">Official Notification</a>\n"
        f"📱 <a href=\"{settings.frontend_url}\">View on AvsarDoot</a>\n\n"
        f"<i>Verify all eligibility details from the official notification before applying.</i>"
    )


def deadline_telegram_message(title: str, apply_end: Any, days_left: int, official_url: str) -> str:
    """Build a Telegram deadline reminder message."""
    return (
        f"<b>⏰ Deadline Reminder</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"📅 Last date to apply: <b>{apply_end}</b>\n"
        f"⚠️ Only <b>{days_left} day(s)</b> left!\n"
        f"🔗 <a href=\"{official_url}\">Apply Now</a>"
    )


def match_email(title: str, reasons: list[str], apply_end: Any, official_url: str, days_left: int | None) -> tuple[str, str]:
    """Build subject and body for a match email notification."""
    why = "; ".join(reasons[:3]) if reasons else "Your profile matches this opportunity"
    deadline = f"Apply by: {apply_end}" if apply_end else "Check official dates"
    if days_left is not None:
        deadline += f" ({days_left} days left)"
    subject = f"New match: {title}"
    body = (
        f"New match: {title}\n\n"
        f"You're eligible: {why}\n"
        f"{deadline}\n"
        f"Official notification: {official_url}\n"
        f"View full details: {settings.frontend_url}\n\n"
        "Disclaimer: Please verify all eligibility details from the official notification before applying."
    )
    return subject, body


def dispatch_match_notifications(
    user_email: str,
    user_phone: str | None,
    user_telegram_chat_id: str | None,
    channels: list[str] | None,
    title: str,
    reasons: list[str],
    apply_end: Any,
    official_url: str,
    days_left: int | None,
):
    selected_channels = channels or ["email"]
    subject, body = match_email(title, reasons, apply_end, official_url, days_left)

    if "email" in selected_channels:
        send_email(user_email, subject, body)

    if "whatsapp" in selected_channels and user_phone:
        whatsapp_msg = (
            f"🎯 *New Match: {title}*\n\n"
            f"✅ *Eligible:* {'; '.join(reasons[:2]) if reasons else 'Profile match'}\n"
            f"📅 *Apply by:* {apply_end or 'See notification'}\n"
            f"🔗 *Official link:* {official_url}"
        )
        send_whatsapp(user_phone, whatsapp_msg)

    if "telegram" in selected_channels and user_telegram_chat_id:
        tg_msg = match_telegram_message(title, reasons, apply_end, official_url, days_left)
        send_telegram(user_telegram_chat_id, tg_msg)

