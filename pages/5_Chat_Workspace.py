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
    check_chat_connection,
)
from guest_browser_storage import (
    initialize_browser_history, save_browser_history,
)
from chat_store import ChatStore, MODES
from chat_auth import verified_chat_owner
from chat_backup import backup_bytes, parse_backup_file
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
    """Only the default st.login() provider is supported by this pilot."""
    try:
        config = st.secrets.get("auth")
        return bool(config and all(config.get(key) for key in (
            "redirect_uri", "cookie_secret", "client_id",
            "client_secret", "server_metadata_url",
        )))
    except Exception:
        return False


def _verified_owner() -> str | None:
    """Fail closed if a signed-in identity has expired or lacks claims."""
    try:
        user = st.user
        if not user.is_logged_in:
            return None
        claims = {key: user.get(key) for key in (
            "iss", "sub", "exp", "iat", "nbf",
        )}
        return verified_chat_owner(claims)
    except ValueError:
        st.warning(
            "Your login has expired or could not be verified. "
            "Sign in again to access saved chats."
        )
        st.logout()
        st.stop()
    except (AttributeError, KeyError, TypeError):
        st.error("Unable to verify the sign-in identity.")
        st.stop()


def _store_for_page() -> tuple[ChatStore, str, bool]:
    """Never silently substitute a disposable chat when saved DB is offline."""
    owner = _verified_owner() if _oidc_configured() else None
    dsn = _secret("ALBA_DATABASE_URL")
    if owner and dsn:
        token = hashlib.sha256(dsn.encode("utf-8")).hexdigest()
        saved = st.session_state.get("alba_persistent_store")
        try:
            if saved and saved[0] == token:
                store = saved[1]
            else:
                store = ChatStore.postgres(dsn)
                st.session_state["alba_persistent_store"] = (token, store)
            if not store.healthcheck():
                raise RuntimeError("database healthcheck failed")
        except Exception:
            st.error(
                "Your saved conversations are temporarily unavailable because "
                "the database cannot be reached. Nothing will be silently "
                "saved into a disposable chat. Try again after the connection "
                "has been restored."
            )
            st.stop()
        return store, owner, True

    if owner and not dsn:
        st.warning(
            "You are signed in, but persistent chat storage has not been "
            "configured. This session is temporary and will not be saved."
        )
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

if not persistent:
    initialize_browser_history(store, owner)

if persistent:
    st.success(
        "Account history: conversations are saved to your configured "
        "PostgreSQL database and are available when you sign in again."
    )
elif st.session_state.get("alba_browser_available"):
    st.info(
        "Saved in this browser: public/synthetic conversations will be restored "
        "after refresh and future visits on this device, as long as this site's "
        "browser storage is not cleared. This is NOT private cloud account "
        "storage or cross-device synchronisation. Do not use shared computers "
        "for sensitive material."
    )
else:
    st.warning(
        "Browser history storage is unavailable. This session is temporary. "
        "Export important conversations using Download resumable chat (.json)."
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
                st.rerun()
            except ValueError:
                st.warning("Enter a project name (up to 75 characters).")

    projects = store.list_projects(owner)
    names = {p["id"]: p["name"] for p in projects}
    if projects:
        with st.expander("Manage existing projects"):
            project_to_remove = st.selectbox(
                "Project to remove", [p["id"] for p in projects],
                format_func=lambda key: names.get(key, "Project"),
                key="alba_delete_project_selected",
            )
            if st.button("Remove project", key="alba_remove_project_start"):
                st.session_state["alba_remove_project_pending"] = project_to_remove
            if st.session_state.get("alba_remove_project_pending") == project_to_remove:
                st.caption(
                    "Removing a project does not delete its chats; chats move "
                    "to No project."
                )
                if st.button(
                    "Confirm remove project", key="alba_remove_project_confirm"
                ):
                    store.delete_project(owner, project_to_remove)
                    st.session_state["alba_remove_project_pending"] = None
                    st.rerun()
    with st.expander("Restore conversation from backup"):
        uploaded_backup = st.file_uploader(
            "ALBA chat backup (.json)", type=["json"],
            key="alba_restore_chat_file",
            help="A JSON chat backup exported from ALBA; not an arbitrary document.",
        )
        backup_public = st.checkbox(
            "I confirm the backup contains public or synthetic content only.",
            key="alba_restore_public_confirm",
        )
        if st.button("Restore chat", key="alba_restore_chat_button"):
            if not uploaded_backup or not backup_public:
                st.warning("Select an ALBA JSON backup and confirm public content.")
            else:
                try:
                    recovered = parse_backup_file(uploaded_backup.getvalue())
                    recovered_id = store.import_conversation_backup(owner, recovered)
                    st.session_state["alba_active_conversation"] = recovered_id
                    st.rerun()
                except ValueError:
                    st.error(
                        "The backup is incomplete, unsupported or contains "
                        "material that is not eligible for this public pilot."
                    )
                except Exception:
                    st.error("Could not restore the chat. The backup was not changed.")

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
        try:
            resumable_backup = backup_bytes(conversation, messages)
        except ValueError:
            st.caption(
                "This conversation is too long or includes content that cannot "
                "be exported as a portable public-only backup."
            )
        else:
            st.download_button(
                "Download resumable chat (.json)", resumable_backup,
                file_name="ALBA_Chat_Backup.json",
                mime="application/json",
                key="alba_backup_" + active_id,
                help="Restore this file later to continue the chat in a new session.",
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
account, api_key = (
    _secret("CLOUDFLARE_ACCOUNT_ID"), _secret("CLOUDFLARE_API_TOKEN"),
)
if not account or not api_key:
    st.error(
        "AI chat is not configured. Check CLOUDFLARE_ACCOUNT_ID and "
        "CLOUDFLARE_API_TOKEN in Streamlit Cloud → App settings → Secrets."
    )

with st.expander("AI connection diagnostics", expanded=False):
    st.caption(
        "This tests Cloudflare with a synthetic phrase. "
        "No uploaded document or conversation is transmitted."
    )
    if st.button("Test AI connection", key="alba_test_ai_connection"):
        if not account or not api_key:
            st.error("Cloudflare credentials are missing.")
        else:
            try:
                with st.spinner("Checking Cloudflare connectivity..."):
                    check_chat_connection(
                        account_id=account, api_token=api_key,
                    )
                st.success("Cloudflare responded successfully. AI chat is available.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Unexpected AI connection problem. Review Streamlit logs.")

st.caption(
    "Ask naturally, as in a conversation. By pressing Send you confirm that "
    "your message contains only public or synthetic content and you authorise "
    "sending it to Cloudflare for an AI response. Do not send private records."
)
prompt = st.chat_input(
    "Ask ALBA anything about a public legal, EU or institutional topic…",
    key="alba_chat_prompt",
    max_chars=MAX_USER_CHARS,
    disabled=not (account and api_key),
)

if prompt:
    st.session_state["alba_pending_chat_text"] = prompt
    st.session_state["alba_pending_chat_error"] = None

pending = st.session_state.get("alba_pending_chat_text")
error = st.session_state.get("alba_pending_chat_error")
retry = False
if pending and error:
    with st.chat_message("user"):
        st.markdown(pending)
    st.error(error)
    retry_col, discard_col = st.columns([1, 1])
    with retry_col:
        retry = st.button(
            "Retry this question", key="alba_retry_chat",
            disabled=not (account and api_key),
        )
    with discard_col:
        if st.button("Discard failed question", key="alba_discard_failed"):
            st.session_state["alba_pending_chat_text"] = None
            st.session_state["alba_pending_chat_error"] = None
            st.rerun()

if (prompt or retry) and pending:
    if scan_text_fields(pending, public_legal=True).blocked:
        st.session_state["alba_pending_chat_error"] = BLOCK_NOTICE
        st.error(BLOCK_NOTICE)
    elif not account or not api_key:
        st.session_state["alba_pending_chat_error"] = (
            "Cloudflare credentials are not configured."
        )
        st.error(st.session_state["alba_pending_chat_error"])
    else:
        if not retry:
            with st.chat_message("user"):
                st.markdown(pending)
        try:
            prepare_chat_messages(
                mode=mode, history=messages, user_text=pending
            )
            with st.chat_message("assistant"):
                with st.spinner("ALBA is responding..."):
                    reply = generate_chat_reply(
                        mode=mode, history=messages, user_text=pending,
                        account_id=account, api_token=api_key,
                    )
        except ValueError as exc:
            # Preserve the exact question and rerender the Retry controls.
            st.session_state["alba_pending_chat_error"] = str(exc)
            st.rerun()
        except Exception:
            st.session_state["alba_pending_chat_error"] = (
                "The chat could not complete due to an unexpected service "
                "problem. Retry this question or test the AI connection."
            )
            st.rerun()
        else:
            try:
                if not active_id:
                    title = pending.strip().replace("\n", " ")[:75]
                    active_id = store.create_conversation(
                        owner, mode=mode, project_id=new_project,
                        title=title,
                    )
                store.append_exchange(owner, active_id, pending, reply)
                st.session_state["alba_active_conversation"] = active_id
                st.session_state["alba_pending_chat_text"] = None
                st.session_state["alba_pending_chat_error"] = None
                st.rerun()
            except Exception:
                st.session_state["alba_pending_chat_error"] = (
                    "The AI responded, but saving the conversation failed. "
                    "Use the visible response below and retry after fixing storage."
                )
                st.error(st.session_state["alba_pending_chat_error"])
                with st.chat_message("assistant"):
                    st.markdown(reply)

if not persistent:
    save_browser_history(
        store, owner,
        active_id=st.session_state.get("alba_active_conversation"),
    )
