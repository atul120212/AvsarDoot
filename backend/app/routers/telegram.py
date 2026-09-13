"""
Telegram Bot integration router.

Endpoints:
  POST /telegram/webhook   — receives updates from Telegram servers (set via setWebhook)
  GET  /telegram/link-token — generates a one-time token the user sends to the bot to link their account
  GET  /telegram/status     — returns whether the current user has linked their Telegram
  POST /telegram/unlink     — removes the user's linked Telegram chat_id
  POST /telegram/test       — sends a test message to the linked Telegram account (dev/debug)
"""

import hashlib
import logging
import os
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.deps import get_current_user
from app.db import get_db
from app.models import User, UserProfile
from app.notifications import send_telegram

log = logging.getLogger("avsardoot.telegram")
router = APIRouter(prefix="/telegram", tags=["telegram"])

# ── polling state (persisted in memory between poll calls) ─────────────────────
_last_update_id: int = 0


def _process_update(update: dict) -> None:
    """Process a single Telegram update — same logic as the webhook handler."""
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    if not chat_id:
        return

    from app.db import SessionLocal
    db = SessionLocal()
    try:
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            token = parts[1].strip() if len(parts) > 1 else ""

            if token:
                profile = (
                    db.query(UserProfile)
                    .filter(UserProfile.telegram_link_token == token)
                    .one_or_none()
                )
                if profile:
                    profile.telegram_chat_id = chat_id
                    profile.telegram_link_token = None
                    channels = list(profile.notification_channels or ["email"])
                    if "telegram" not in channels:
                        channels.append("telegram")
                    profile.notification_channels = channels
                    db.commit()
                    bot_name = settings.telegram_bot_username or "AvsarDoot Bot"
                    send_telegram(
                        chat_id,
                        f"<b>✅ Account linked successfully!</b>\n\n"
                        f"You'll now receive job & exam alerts directly here.\n\n"
                        f"<i>This is @{bot_name} — your personal Govt Jobs assistant.</i>",
                    )
                    log.info("Telegram linked via polling: chat_id=%s", chat_id)
                else:
                    send_telegram(
                        chat_id,
                        "❌ <b>Invalid or expired link token.</b>\n\n"
                        "Please go back to AvsarDoot and generate a fresh link.",
                    )
            else:
                send_telegram(
                    chat_id,
                    "<b>👋 Welcome to AvsarDoot!</b>\n\n"
                    "To receive job & exam alerts, open <b>AvsarDoot → 📱 Telegram</b> "
                    "in the app and click <b>Generate Bot Link</b>.\n\n"
                    "That will automatically connect your account.",
                )

        elif text.startswith("/help"):
            send_telegram(
                chat_id,
                "<b>AvsarDoot Bot Commands</b>\n\n"
                "/start — Link your AvsarDoot account\n"
                "/help — Show this help message\n"
                "/status — Check if your account is linked",
            )

        elif text.startswith("/status"):
            profile = (
                db.query(UserProfile)
                .filter(UserProfile.telegram_chat_id == chat_id)
                .one_or_none()
            )
            if profile:
                send_telegram(chat_id, "✅ <b>Your Telegram is linked to AvsarDoot.</b>\nYou'll receive job alerts here automatically.")
            else:
                send_telegram(chat_id, "❌ <b>Not linked yet.</b>\nOpen AvsarDoot → 📱 Telegram to connect.")
    finally:
        db.close()


def telegram_poll_job() -> None:
    """
    APScheduler job: polls Telegram getUpdates every 3 seconds.
    Works on localhost without needing a public webhook URL.
    """
    global _last_update_id
    if not settings.telegram_bot_token:
        return
    try:
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates"
        params = {"timeout": 1, "offset": _last_update_id + 1, "limit": 10}
        resp = httpx.get(url, params=params, timeout=4)
        if resp.status_code != 200:
            return
        data = resp.json()
        if not data.get("ok"):
            return
        for update in data.get("result", []):
            _last_update_id = update["update_id"]
            try:
                _process_update(update)
            except Exception:
                log.exception("Error processing Telegram update %s", update.get("update_id"))
    except Exception:
        log.exception("telegram_poll_job error")


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_or_create_profile(db: Session, user: User) -> UserProfile:
    profile = db.query(UserProfile).filter(UserProfile.user_id == user.id).one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Complete your profile first before linking Telegram.")
    return profile


def _bot_api(method: str, payload: dict) -> dict:
    """Call a Telegram Bot API method."""
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    resp = httpx.post(url, json=payload, timeout=10)
    return resp.json()


@router.post("/setup-webhook")
def setup_telegram_webhook(webhook_url: str | None = None):
    """
    Configure the Telegram bot webhook for Vercel production deployment.
    If webhook_url is not provided, defaults to {frontend_url}/api/telegram/webhook.
    """
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured.")
    target_url = webhook_url or f"{settings.frontend_url.rstrip('/')}/api/telegram/webhook"
    res = _bot_api("setWebhook", {"url": target_url})
    return {"ok": res.get("ok", False), "result": res, "target_url": target_url}



# ── webhook ────────────────────────────────────────────────────────────────────

@router.post("/webhook", include_in_schema=False)
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives all Telegram updates (messages, commands).
    When a user sends /start <token>, we link their chat_id to the matching user account.
    """
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()

    # Handle /start <link_token>
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        token = parts[1].strip() if len(parts) > 1 else ""

        if token:
            # Find a profile with this link token
            profile = (
                db.query(UserProfile)
                .filter(UserProfile.telegram_link_token == token)
                .one_or_none()
            )
            if profile:
                profile.telegram_chat_id = chat_id
                profile.telegram_link_token = None  # consume the token
                channels = list(profile.notification_channels or ["email"])
                if "telegram" not in channels:
                    channels.append("telegram")
                profile.notification_channels = channels
                db.commit()
                bot_name = settings.telegram_bot_username or "AvsarDoot Bot"
                send_telegram(
                    chat_id,
                    f"<b>✅ Account linked successfully!</b>\n\n"
                    f"You'll now receive job & exam alerts directly here.\n\n"
                    f"<i>This is {bot_name} — your personal Govt Jobs assistant.</i>",
                )
                log.info("Telegram linked: chat_id=%s to profile=%s", chat_id, profile.id)
            else:
                send_telegram(
                    chat_id,
                    "❌ <b>Invalid or expired link token.</b>\n\n"
                    "Please go back to AvsarDoot and generate a fresh link.",
                )
        else:
            # /start without token — generic welcome
            send_telegram(
                chat_id,
                "<b>👋 Welcome to AvsarDoot!</b>\n\n"
                "To receive job & exam alerts, open <b>AvsarDoot → Profile → Link Telegram</b> "
                "and click the bot link there.\n\n"
                "That will automatically connect your account.",
            )

    # Handle /help
    elif text.startswith("/help"):
        send_telegram(
            chat_id,
            "<b>AvsarDoot Bot Commands</b>\n\n"
            "/start — Link your AvsarDoot account\n"
            "/help — Show this help message\n"
            "/status — Check if your account is linked\n\n"
            "Visit <a href=\"http://localhost:3000\">AvsarDoot</a> for the full experience.",
        )

    # Handle /status
    elif text.startswith("/status"):
        profile = (
            db.query(UserProfile)
            .filter(UserProfile.telegram_chat_id == chat_id)
            .one_or_none()
        )
        if profile:
            send_telegram(chat_id, "✅ <b>Your Telegram is linked to AvsarDoot.</b>\nYou'll receive job alerts here automatically.")
        else:
            send_telegram(chat_id, "❌ <b>Not linked yet.</b>\nOpen AvsarDoot → Profile → Link Telegram to connect.")

    return {"ok": True}


# ── link-token ─────────────────────────────────────────────────────────────────

@router.get("/link-token")
def get_link_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a one-time link token. The user opens the deep-link in Telegram
    which sends /start <token> to the bot, triggering account linking.
    """
    profile = _get_or_create_profile(db, current_user)

    # Generate a fresh secure token
    token = secrets.token_urlsafe(32)
    profile.telegram_link_token = token
    db.commit()

    bot_username = settings.telegram_bot_username
    if not bot_username:
        raise HTTPException(
            status_code=503,
            detail="TELEGRAM_BOT_USERNAME is not configured. Ask the admin to set it in .env.",
        )

    deep_link = f"https://t.me/{bot_username}?start={token}"
    return {
        "token": token,
        "deep_link": deep_link,
        "bot_username": bot_username,
        "already_linked": bool(profile.telegram_chat_id),
    }


# ── status ─────────────────────────────────────────────────────────────────────

@router.get("/status")
def telegram_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns whether the current user has linked their Telegram account."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == current_user.id).one_or_none()
    linked = bool(profile and profile.telegram_chat_id)
    return {
        "linked": linked,
        "chat_id": profile.telegram_chat_id if linked else None,
    }


# ── unlink ─────────────────────────────────────────────────────────────────────

@router.post("/unlink")
def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Removes the Telegram link from the user's account."""
    profile = _get_or_create_profile(db, current_user)
    profile.telegram_chat_id = None
    profile.telegram_link_token = None
    db.commit()
    return {"ok": True, "message": "Telegram account unlinked."}


# ── test message ───────────────────────────────────────────────────────────────

@router.post("/test")
def send_test_message(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sends a test notification to verify the Telegram link is working."""
    profile = _get_or_create_profile(db, current_user)
    if not profile.telegram_chat_id:
        raise HTTPException(status_code=400, detail="Telegram not linked. Use /telegram/link-token first.")

    success = send_telegram(
        profile.telegram_chat_id,
        "<b>🎯 AvsarDoot Test Notification</b>\n\n"
        "This is a test message to confirm your Telegram alerts are working correctly.\n\n"
        "You'll receive real job & exam alerts here when matches are found for your profile. ✅",
    )
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send Telegram message. Check TELEGRAM_BOT_TOKEN.")
    return {"ok": True, "message": "Test message sent to your Telegram."}
