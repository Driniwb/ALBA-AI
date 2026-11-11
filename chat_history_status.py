"""Truthful storage-status labels for the ALBA Chat Workspace.

Only the authenticated PostgreSQL path is account-synced. Guest snapshots
are stored on the current browser origin; local writes require a matching
JavaScript read-back acknowledgement for the current revision.
"""
from __future__ import annotations


def chat_history_status(
    *, account_saved: bool, browser_available: bool = False,
    browser_confirmed: bool = False, browser_error: str | None = None,
) -> str:
    if account_saved:
        return "Saved to your account · available on signed-in devices"
    if browser_error or not browser_available:
        return "Not saved · browser storage is unavailable or full"
    if browser_confirmed:
        return "Saved in this browser · not synced to other devices"
    return "Saving in this browser…"
