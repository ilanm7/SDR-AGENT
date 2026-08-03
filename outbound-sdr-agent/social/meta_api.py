"""
Meta Graph API helpers — Instagram & Facebook
Handles webhook verification, comment replies, and DM sending.
"""
import os
import requests

GRAPH_VERSION = "v20.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def verify_webhook(mode: str, token: str, challenge: str) -> str | None:
    """Return hub.challenge if webhook verification passes, else None."""
    verify_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "targetco_webhook_secret")
    if mode == "subscribe" and token == verify_token:
        return challenge
    return None


def reply_to_comment(comment_id: str, message: str, access_token: str) -> dict:
    """Reply to an Instagram or Facebook comment."""
    url = f"{GRAPH_BASE}/{comment_id}/replies"
    resp = requests.post(
        url,
        data={"message": message, "access_token": access_token},
        timeout=10,
    )
    return resp.json()


def send_dm(recipient_id: str, message: str, page_id: str, access_token: str) -> dict:
    """Send a DM via Meta Messaging API (Instagram or Facebook)."""
    url = f"{GRAPH_BASE}/{page_id}/messages"
    resp = requests.post(
        url,
        json={
            "recipient": {"id": recipient_id},
            "message": {"text": message},
            "messaging_type": "RESPONSE",
        },
        params={"access_token": access_token},
        timeout=10,
    )
    return resp.json()


def parse_webhook_event(payload: dict) -> list:
    """
    Normalise a Meta webhook payload into a flat list of message dicts.
    Supports Instagram comments, Facebook page comments, and Instagram DMs.
    """
    messages = []
    for entry in payload.get("entry", []):
        # ── Instagram/Facebook comments (changes field) ──────────────────
        for change in entry.get("changes", []):
            field = change.get("field", "")
            value = change.get("value", {})

            if field == "comments":
                messages.append({
                    "platform": "instagram",
                    "type": "comment",
                    "id": value.get("id", ""),
                    "from": value.get("from", {}).get("username", "unknown"),
                    "content": value.get("text", ""),
                    "context": str(value.get("media", {}).get("id", "")),
                    "raw": value,
                })
            elif field == "feed":
                # Facebook page feed comments
                messages.append({
                    "platform": "facebook",
                    "type": "comment",
                    "id": value.get("comment_id", value.get("post_id", "")),
                    "from": value.get("from", {}).get("name", "unknown"),
                    "content": value.get("message", ""),
                    "context": str(value.get("post_id", "")),
                    "raw": value,
                })

        # ── Instagram DMs (messaging field) ─────────────────────────────
        for msg in entry.get("messaging", []):
            inner = msg.get("message", {})
            if inner.get("text"):
                messages.append({
                    "platform": "instagram",
                    "type": "dm",
                    "id": inner.get("mid", ""),
                    "from": msg.get("sender", {}).get("id", "unknown"),
                    "content": inner["text"],
                    "context": "",
                    "raw": msg,
                })
    return messages
