"""Portable, public-only ALBA chat backups.

A downloadable JSON export lets temporary-mode users continue a prior chat
after reconnecting by explicitly re-importing their backup file. It is not
automatic cloud persistence or an encrypted archival format.
"""
from __future__ import annotations

import json

from chat_store import MODES, MAX_CHAT_TITLE, MAX_MESSAGE_CHARS
from privacy_guard import scan_text_fields

BACKUP_FORMAT = "alba-chat-backup"
BACKUP_VERSION = 1
MAX_BACKUP_BYTES = 2 * 1024 * 1024
MAX_BACKUP_MESSAGES = 300


def validate_backup(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Invalid ALBA backup format.")
    if (payload.get("format") != BACKUP_FORMAT
            or payload.get("version") != BACKUP_VERSION):
        raise ValueError("Unsupported ALBA chat backup version.")
    title, mode, messages = (
        payload.get("title"), payload.get("mode"), payload.get("messages")
    )
    if (not isinstance(title, str) or not title.strip()
            or len(title) > MAX_CHAT_TITLE or scan_text_fields(
                title, public_legal=True
            ).blocked):
        raise ValueError("Invalid or unsafe chat title.")
    if mode not in MODES:
        raise ValueError("Invalid chat specialist mode.")
    if (not isinstance(messages, list)
            or len(messages) == 0
            or len(messages) > MAX_BACKUP_MESSAGES
            or len(messages) % 2):
        raise ValueError("Backup must contain complete conversation exchanges.")

    restored = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise ValueError("Invalid chat message in backup.")
        role = "user" if index % 2 == 0 else "assistant"
        body = message.get("content")
        if (message.get("role") != role or not isinstance(body, str)
                or not body.strip() or len(body) > MAX_MESSAGE_CHARS
                or scan_text_fields(body, public_legal=True).blocked):
            raise ValueError(
                "Chat backup has invalid, incomplete or sensitive messages."
            )
        restored.append({"role": role, "content": body})

    cleaned = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "title": title.strip(),
        "mode": mode,
        "messages": restored,
    }
    if len(json.dumps(cleaned, ensure_ascii=False).encode("utf-8")) > MAX_BACKUP_BYTES:
        raise ValueError("Chat backup exceeds the safe import size.")
    return cleaned


def backup_bytes(conversation: dict, messages: list[dict]) -> bytes:
    """No owner IDs, database URI, access token or internal session fields."""
    backup = validate_backup({
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "title": conversation.get("title"),
        "mode": conversation.get("mode"),
        "messages": [
            {"role": msg.get("role"), "content": msg.get("content")}
            for msg in messages
        ],
    })
    return json.dumps(
        backup, ensure_ascii=False, indent=2
    ).encode("utf-8")


def parse_backup_file(content: bytes) -> dict:
    """Strict file format, no HTML, Python code, credential or file execution."""
    if (not isinstance(content, bytes) or not content
            or len(content) > MAX_BACKUP_BYTES):
        raise ValueError("Backup is empty or larger than 2 MB.")
    try:
        payload = json.loads(content.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Backup is not valid UTF-8 JSON.") from exc
    return validate_backup(payload)
