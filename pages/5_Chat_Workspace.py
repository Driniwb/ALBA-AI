"""ALBA Chat Workspace: projects, saved threads and multi-turn continuation.

Cloud-deployed persistent history is available ONLY after verified OIDC
sign-in and external PostgreSQL configuration. Otherwise the clearly labeled
demo runs in per-browser-session SQLite memory and is lost on session restart.
"""
from __future__ import annotations

import hashlib
from uuid import uuid4

import streamlit as st

from chat_backend import (
    MAX_USER_CHARS, generate_chat_reply, prepare_chat_messages,
)
from chat_store import ChatStore, MODES, owner_key_from_oidc
from privacy_guard import BLOCK_NOTICE, scan_text_fields
from ui_theme import apply_theme

st.set_page_config(page_title="ALBA | Chat Workspace", page_icon="💬", layout="wide")
apply_theme("WORKSPACE")
st.title("Chat Workspace")
st.caption("Multi-turn legal and institutional AI · Projects · Conversation history")
st.warning(
    "Public or synthetic material only. Do not paste confidential government "
    "drafts, personal records, private contacts or credentials. Chat responses "
    "are not certified legal advice or EU acquis conformity assessments."
)


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""


def _oidc_configured() -> bool:
    try:
        config = st.secrets.get("auth")
        return bool(config and config.get("redirect_uri")
                    and config.get("cookie_secret"))
    except Exception:
        return False


def _verified_owner() -> str | None:
    try:
        user = st.user
        if not user.is_logged_in:
            return None
        return owner_key_from_oidc(user.get("iss", ""), user.get("sub", ""))
    except (ValueError, AttributeError, KeyError):
        return None


def _store_for_page() -> tuple[ChatStore, str, bool]:
    """Prefer durable auth+Postgres. No unprotected cross-user persistence."""
    owner = _verified_owner() if _oidc_configured() else None
    dsn = _secret("ALBA_DATABASE_URL")
    if owner and dsn:
        token = hashlib.sha256(dsn.encode("utf-8")).hexdigest()
        saved = st.session_state.get("alba_persistent_store")
        if saved and saved[0] == token:
            return saved[1], owner, True
        try:
            store = ChatStore.postgres(dsn)
        except Exception:
            st.error(
                "Persistent database is unavailable. Using a temporary session "
                "only; these messages will NOT be saved after your session ends."
            )
        else:
            st.session_state["alba_persistent_store"] = (token, store)
            return store, owner, True

    if "alba_demo_store" not in st.session_state:
        st.session_state["alba_demo_store"] = ChatStore.session_memory()
        # Random session-only owner prevents cross-session guest access.
        st.session_state["alba_demo_owner"] = hashlib.sha256(
            uuid4().bytes
        ).hexdigest()
    return (
        st.session_state["alba_demo_store"],
        st.session_state["alba_demo_owner"],
        False,
    )


store, owner, persistent = _store_for_page()
scope = ("account:" if persistent else "temporary:") + owner
if st.session_state.get("alba_scope") != scope:
    st.session_state["alba_scope"] = scope
    st.session_state["alba_active_conversation"] = None

if persistent:
    st.success(
        "Saved workspace: conversations and projects are stored for your "
        "signed-in account and can be resumed after returning to ALBA."
    )
else:
    st.info(
        "Temporary workspace. Chats continue while this browser session is "
        "open, but will disappear after refresh/restart or redeployment. "
        "For permanent, private history configure OIDC login and "
        "ALBA_DATABASE_URL (PostgreSQL) in Streamlit Cloud."
    )

if _oidc_configured():
    with st.sidebar:
        if _verified_owner():
            if st.button("Log out", key="alba_logout"):
                st.logout()
        elif st.button("Sign in to save conversations", key="alba_login"):
            st.login()

with st.sidebar:
    st.divider()
    st.subheader("Conversations")
    if st.button("＋ New chat", key="alba_new_chat", use_container_width=True):
        st.session_state["alba_active_conversation"] = None
        st.rerun()

    with st.expander("Projects", expanded=False):
        project_name = st.text_input(
            "New project", placeholder="e.g. Chapter 14 – Transport",
            max_chars=75, key="alba_project_name",
        )
        if st.button("Create project", key="alba_create_project"):
            try:
                store.create_project(owner, project_name)
                st.session_state["alba_project_name"] = ""
                st.rerun()
            except ValueError:
                st.warning("Enter a project name (up to 75 characters).")

    projects = store.list_projects(owner)
    names = {p["id"]: p["name"] for p in projects}
    conversations = store.list_conversations(owner)

    for chat in conversations[:45]:
        current = chat["id"] == st.session_state["alba_active_conversation"]
        prefix = (names.get(chat["project_id"], "General") + " · ")
        label = prefix + chat["title"]
        if st.button(
            label[:90], key="alba_open_" + chat["id"],
            use_container_width=True,
            type="primary" if current else "secondary",
        ):
            st.session_state["alba_active_conversation"] = chat["id"]
            st.rerun()
    if len(conversations) > 45:
        st.caption("Showing 45 most recent chats.")
    if not conversations:
        st.caption("No previous conversations in this workspace.")

active_id = st.session_state.get("alba_active_conversation")
conversation = (
    store.get_conversation(owner, active_id) if active_id else None
)
if active_id and conversation is None:
    st.session_state["alba_active_conversation"] = None
    active_id = None

project_ids = [None] + [p["id"] for p in projects]
project_label = lambda value: "No project" if value is None else names.get(value, "Project")

if conversation:
    st.subheader(conversation["title"])
    st.caption("Specialism: " + MODES[conversation["mode"]])
    actions, move, export = st.columns([2, 2, 2])
    with actions:
        new_title = st.text_input(
            "Rename conversation", value=conversation["title"],
            max_chars=90, key="alba_rename_title_" + active_id,
        )
        if st.button("Save title", key="alba_rename_" + active_id):
            if store.rename_conversation(owner, active_id, new_title):
                st.rerun()
    with move:
        index = (
            project_ids.index(conversation["project_id"])
            if conversation["project_id"] in project_ids else 0
        )
        chosen_project = st.selectbox(
            "Project", project_ids, index=index, format_func=project_label,
            key="alba_move_project_" + active_id,
        )
        if st.button("Move chat", key="alba_move_" + active_id):
            store.set_conversation_project(owner, active_id, chosen_project)
            st.rerun()

    messages = store.list_messages(owner, active_id)
    with export:
        transcript = "# " + conversation["title"] + "\n\n" + "\n\n".join(
            ("## " + ("You" if msg["role"] == "user" else "ALBA") + "\n\n"
             + msg["content"])
            for msg in messages
        )
        st.download_button(
            "Export transcript (.md)", transcript.encode("utf-8"),
            file_name="ALBA_Chat_Transcript.md", mime="text/markdown",
            key="alba_export_" + active_id,
        )
        if st.button("Delete conversation", key="alba_delete_start_" + active_id):
            st.session_state["alba_delete_confirm"] = active_id

    if st.session_state.get("alba_delete_confirm") == active_id:
        st.warning("Delete this conversation and every message in it?")
        if st.button("Confirm permanent deletion", key="alba_delete_confirm_button"):
            store.delete_conversation(owner, active_id)
            st.session_state["alba_active_conversation"] = None
            st.session_state["alba_delete_confirm"] = None
            st.rerun()
        if st.button("Cancel", key="alba_delete_cancel_button"):
            st.session_state["alba_delete_confirm"] = None
            st.rerun()
    mode = conversation["mode"]
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
else:
    st.subheader("Start a new conversation")
    mode = st.selectbox(
        "Assistant specialism", list(MODES),
        format_func=lambda value: MODES[value],
        key="alba_chat_mode",
    )
    new_project = st.selectbox(
        "Add to project", project_ids, format_func=project_label,
        key="alba_new_project",
    )
    messages = []
    st.caption(
        "Try: Compare a proposed VKM provision with the supplied Directive "
        "article; review an Administrative Capacity Note; or draft an EU reply."
    )

st.caption(
    "ALBA remembers the full thread in the workspace, but sends only recent "
    "turns within the AI context limit. Verify citations against official texts."
)
confirm = st.checkbox(
    "I confirm this conversation contains only public or synthetic material.",
    key="alba_chat_public_confirm",
)

prompt = st.chat_input(
    "Ask a question or continue this ALBA conversation…",
    key="alba_chat_prompt",
    max_chars=MAX_USER_CHARS,
)

if prompt:
    if not confirm:
        st.warning("Confirm public/synthetic material before sending a message.")
    elif scan_text_fields(prompt, public_legal=True).blocked:
        st.error(BLOCK_NOTICE)
    else:
        account, api_key = (
            _secret("CLOUDFLARE_ACCOUNT_ID"),
            _secret("CLOUDFLARE_API_TOKEN"),
        )
        if not account or not api_key:
            st.error(
                "Cloudflare is not configured. The message was not sent or saved."
            )
        else:
            try:
                # No chat is created until the AI responds successfully.
                prepare_chat_messages(
                    mode=mode, history=messages, user_text=prompt
                )
                with st.spinner("ALBA is responding..."):
                    reply = generate_chat_reply(
                        mode=mode, history=messages, user_text=prompt,
                        account_id=account, api_token=api_key,
                    )
            except ValueError as exc:
                # Provider errors are generic; never include key material.
                st.error(str(exc))
            else:
                try:
                    if not active_id:
                        title = prompt.strip().replace("\n", " ")[:75]
                        active_id = store.create_conversation(
                            owner, mode=mode, project_id=new_project,
                            title=title,
                        )
                    store.append_exchange(owner, active_id, prompt, reply)
                    st.session_state["alba_active_conversation"] = active_id
                    st.rerun()
                except Exception:
                    st.error(
                        "ALBA generated a response, but it could not be saved. "
                        "Copy the response below before leaving this page."
                    )
                    with st.chat_message("assistant"):
                        st.markdown(reply)
