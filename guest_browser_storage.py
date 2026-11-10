"""Browser-local persistence for PUBLIC/SYNTHETIC guest ALBA chats.

A Streamlit Component v2 copies a versioned snapshot to localStorage on the
same browser origin. No credentials, cloud DB, cross-browser sync or encryption.
The component is fixed trusted JS and only receives JSON as serialized data,
never concatenated executable code. The backend revalidates every imported
chat and assigns it to the current ephemeral owner.
"""
from __future__ import annotations

import hashlib
import json
import os

import streamlit as st

from chat_backup import validate_backup, backup_bytes
from chat_store import ChatStore, MAX_PROJECT_NAME
from privacy_guard import scan_text_fields

WORKSPACE_FORMAT = "alba-browser-chats"
WORKSPACE_VERSION = 1
MAX_WORKSPACE_BYTES = 1_800_000
MAX_PROJECTS = 50
MAX_CHATS = 80
MAX_MESSAGES = 500
BROWSER_KEY = "alba-public-workspace-v1"
EMPTY = "__ALBA_EMPTY__"
UNAVAILABLE = "__ALBA_UNAVAILABLE__"

# No user-generated data is inserted into this script. Component v2 runs at
# the ALBA app origin and accesses localStorage for that origin only.
_BROWSER_JS = """
export default function ({parentElement, data, setStateValue}) {
  const key = "alba-public-workspace-v1";
  const label = parentElement.querySelector(".alba-browser-sync");
  if (data?.phase === "load") {
    try {
      const raw = window.localStorage.getItem(key);
      if (label) label.textContent = "Restoring browser history…";
      setStateValue("loaded", raw === null ? "__ALBA_EMPTY__" : raw);
      setStateValue("error", "");
    } catch (error) {
      setStateValue("loaded", "__ALBA_UNAVAILABLE__");
      setStateValue("error", "Browser storage is unavailable or blocked.");
    }
  } else if (data?.phase === "save") {
    try {
      if (typeof data?.payload !== "string") throw new Error("No snapshot");
      // Avoid redundant writes and reruns for identical snapshots.
      if (window.localStorage.getItem(key) !== data.payload) {
        window.localStorage.setItem(key, data.payload);
      }
      if (label) label.textContent = "Saved in this browser";
      setStateValue("saved", data?.revision ?? "");
      setStateValue("error", "");
    } catch (error) {
      setStateValue("error", "Browser storage is unavailable or full.");
    }
  }
}
"""
_BROWSER_HTML = '<span class="alba-browser-sync" style="font-size:0.8em;opacity:0.65">Browser history</span>'


def _bridge():
    return st.components.v2.component(
        name="alba_browser_guest_history",
        html=_BROWSER_HTML,
        js=_BROWSER_JS,
        isolate_styles=True,
    )


def _mount(data: dict):
    component = _bridge()
    return component(
        key="alba_browser_guest_history_widget",
        data=data,
        default={"loaded": None, "saved": None, "error": ""},
        on_loaded_change=lambda: None,
        on_saved_change=lambda: None,
        on_error_change=lambda: None,
    )


def _for_tests() -> bool:
    """Frontend JS is not executed in Streamlit AppTest's headless runner."""
    return os.environ.get("ALBA_HEADLESS_TEST") == "1"


def export_guest_workspace(
    store: ChatStore, owner: str, *, active_id: str | None = None
) -> str:
    """Export fully screened workspace; bounds prevent browser quota abuse."""
    projects = store.list_projects(owner)
    chats = store.list_conversations(owner)
    if len(projects) > MAX_PROJECTS or len(chats) > MAX_CHATS:
        raise ValueError("Browser history limit reached; export chat backups.")
    project_index = {p["id"]: i for i, p in enumerate(projects)}
    collected = []
    count = 0
    active_index = None
    for item in chats:
        messages = store.list_messages(owner, item["id"])
        if not messages:
            # New chats only appear once an exchange has been saved.
            continue
        count += len(messages)
        if count > MAX_MESSAGES:
            raise ValueError("Browser history message limit reached.")
        backup = json.loads(backup_bytes(item, messages).decode("utf-8"))
        if item["id"] == active_id:
            active_index = len(collected)
        collected.append({
            "project": project_index.get(item["project_id"]),
            "chat": backup,
        })
    snapshot = {
        "format": WORKSPACE_FORMAT,
        "version": WORKSPACE_VERSION,
        "projects": [p["name"] for p in projects],
        "chats": collected,
        "active": active_index,
    }
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    if len(payload.encode("utf-8")) > MAX_WORKSPACE_BYTES:
        raise ValueError("Browser history exceeds 1.8 MB.")
    return payload


def validate_guest_workspace(text: str) -> dict:
    """Untrusted localStorage contents are treated like untrusted file uploads."""
    if not isinstance(text, str):
        raise ValueError("Browser data is not a valid string.")
    raw = text.encode("utf-8")
    if len(raw) > MAX_WORKSPACE_BYTES:
        raise ValueError("Browser history is too large.")
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise ValueError("Browser history is not valid JSON.") from exc
    if (not isinstance(data, dict)
            or data.get("format") != WORKSPACE_FORMAT
            or data.get("version") != WORKSPACE_VERSION):
        raise ValueError("Browser history is not an ALBA workspace.")
    projects = data.get("projects")
    chats = data.get("chats")
    active = data.get("active")
    if (not isinstance(projects, list) or len(projects) > MAX_PROJECTS
            or not isinstance(chats, list) or len(chats) > MAX_CHATS):
        raise ValueError("Browser history has invalid project or chat lists.")
    names = []
    for name in projects:
        if (not isinstance(name, str) or not name.strip()
                or len(name) > MAX_PROJECT_NAME or
                scan_text_fields(name, public_legal=True).blocked):
            raise ValueError("Invalid public project name in browser history.")
        names.append(name)
    clean_chats = []
    count = 0
    for item in chats:
        if not isinstance(item, dict):
            raise ValueError("Invalid conversation in browser history.")
        project = item.get("project")
        if project is not None and (
            isinstance(project, bool) or not isinstance(project, int)
            or project < 0 or project >= len(names)
        ):
            raise ValueError("Invalid project reference in browser history.")
        backup = validate_backup(item.get("chat"))
        count += len(backup["messages"])
        if count > MAX_MESSAGES:
            raise ValueError("Browser history has too many messages.")
        clean_chats.append({"project": project, "chat": backup})
    if active is not None and (
        isinstance(active, bool) or not isinstance(active, int)
        or active < 0 or active >= len(clean_chats)
    ):
        raise ValueError("Invalid active conversation index.")
    return {"projects": names, "chats": clean_chats, "active": active}


def restore_guest_workspace(
    store: ChatStore, owner: str, snapshot: str
) -> str | None:
    """Restore only into a fresh, current-session store; never other users."""
    clean = validate_guest_workspace(snapshot)
    if store.list_projects(owner) or store.list_conversations(owner):
        raise ValueError("Restore requires a new temporary workspace.")
    project_ids = [store.create_project(owner, name) for name in clean["projects"]]
    chat_ids = []
    for item in clean["chats"]:
        chat_id = store.import_conversation_backup(owner, item["chat"])
        if item["project"] is not None:
            store.set_conversation_project(
                owner, chat_id, project_ids[item["project"]]
            )
        chat_ids.append(chat_id)
    return (
        chat_ids[clean["active"]]
        if clean["active"] is not None else None
    )


def initialize_browser_history(store: ChatStore, owner: str) -> None:
    """Load browser snapshot before allowing guest writes to avoid overwrite."""
    if _for_tests():
        st.session_state["alba_browser_ready"] = True
        return
    if st.session_state.get("alba_browser_ready"):
        return
    reply = _mount({"phase": "load"})
    raw = reply.loaded
    if raw is None:
        st.info("Loading your saved conversations from this browser…")
        st.stop()
    if raw == UNAVAILABLE:
        st.session_state["alba_browser_ready"] = True
        st.session_state["alba_browser_available"] = False
        return
    if raw != EMPTY:
        try:
            restored_id = restore_guest_workspace(store, owner, raw)
            st.session_state["alba_active_conversation"] = restored_id
        except ValueError:
            st.error(
                "A previous browser history exists but cannot be loaded. "
                "To avoid overwriting it, browser saving has been disabled. "
                "Use a valid ALBA chat backup or clear this site's browser "
                "storage manually after exporting a copy."
            )
            st.session_state["alba_browser_available"] = False
            st.session_state["alba_browser_ready"] = True
            return
    st.session_state["alba_browser_available"] = True
    st.session_state["alba_browser_ready"] = True


def save_browser_history(
    store: ChatStore, owner: str, *, active_id: str | None = None
) -> None:
    """Sync screened messages automatically after every Streamlit rerun."""
    if _for_tests() or not st.session_state.get("alba_browser_available"):
        return
    try:
        payload = export_guest_workspace(store, owner, active_id=active_id)
    except ValueError:
        st.warning(
            "Browser storage limit reached. Export important conversations "
            "using Download resumable chat (.json)."
        )
        return
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    result = _mount({
        "phase": "save", "payload": payload, "revision": digest,
    })
    if result.error:
        st.warning(
            "This browser cannot save chat history. Export conversations as "
            "JSON backups. No account or cloud database is configured."
        )
