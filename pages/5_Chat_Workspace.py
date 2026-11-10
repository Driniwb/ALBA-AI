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
from privacy_guard import BLOCK_NOTICE, scan_text_fields, screen_upload, upload_block_message
from ui_theme import apply_theme

st.set_page_config(page_title="ALBA | Chat Workspace", page_icon="💬", layout="wide")
apply_theme("WORKSPACE")
st.title("Chat Workspace")
st.caption("Ask questions, work with documents, and continue earlier chats.")


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
        st.caption("Account sync isn't configured; using browser history.")
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
    st.caption("History saved to your account.")
elif st.session_state.get("alba_browser_available"):
    st.caption("History saved in this browser only.")
else:
    st.warning("Browser saving unavailable. Export chats to keep them.")

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
                st.caption("Chats remain under No project.")
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

def _render_chat_content(value: str) -> None:
    marker = "\n\n[PUBLIC DOCUMENT EXCERPT: "
    if marker not in value:
        st.markdown(value)
        return
    question, raw_source = value.split(marker, 1)
    st.markdown(question)
    with st.expander("Attached public document excerpt"):
        st.code(raw_source, language=None)


if conversation:
    st.subheader(conversation["title"])
    st.caption(MODES[conversation["mode"]])
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
            _render_chat_content(message["content"])
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
    st.caption("Example: Compare this VKM provision with the EU directive.")

attachment_text = ""
attachment_name = ""
with st.expander("Attach a public document (optional)"):
    doc_nonce = st.session_state.get("alba_doc_nonce", 0)
    doc = st.file_uploader(
        "Attach public legislation, directive or report",
        type=["pdf", "docx", "txt", "md"],
        key="alba_public_doc_" + str(doc_nonce),
    )
    if doc:
        checked = screen_upload(
            doc.name, doc.getvalue(),
            public_legal=True, max_chars=150000,
        )
        if checked.blocked:
            st.error(upload_block_message(checked.reason))
        else:
            if checked.warning:
                st.warning(checked.warning)
            if len(checked.text) > 3200:
                st.caption("Long document: select the section to analyse.")
                digest = hashlib.sha256(doc.getvalue()).hexdigest()[:12]
                with st.expander("Read extracted public source"):
                    st.text_area(
                        "Full extracted text (read-only)",
                        value=checked.text, height=260, disabled=True,
                        key="alba_full_source_" + digest,
                    )
                attachment_text = st.text_area(
                    "Source excerpt for your next question",
                    value=checked.text[:3200], max_chars=3200,
                    height=180, key="alba_source_selection_" + digest,
                )
            else:
                attachment_text = checked.text
            if attachment_text.strip():
                attachment_name = doc.name

account, api_key = (
    _secret("CLOUDFLARE_ACCOUNT_ID"), _secret("CLOUDFLARE_API_TOKEN"),
)
if not account or not api_key:
    st.error(
        "AI chat is not configured. Check CLOUDFLARE_ACCOUNT_ID and "
        "CLOUDFLARE_API_TOKEN in Streamlit Cloud → App settings → Secrets."
    )

with st.expander("Connection settings"):
    if st.button("Test AI connection", key="alba_test_ai_connection"):
        if not account or not api_key:
            st.error("Cloudflare credentials are missing.")
        else:
            try:
                with st.spinner("Checking Cloudflare connectivity..."):
                    check_chat_connection(
                        account_id=account, api_token=api_key,
                    )
                st.success("AI connection working.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Unexpected AI connection problem. Review Streamlit logs.")

st.caption(
    "Public or synthetic content only. Sending a message shares it with Cloudflare."
)
doc_context = (
    "\n\n[PUBLIC DOCUMENT EXCERPT: " + attachment_name + "]\n"
    + attachment_text + "\n[/PUBLIC DOCUMENT EXCERPT]"
    if attachment_name else ""
)
available_chars = max(100, MAX_USER_CHARS - len(doc_context))
prompt = st.chat_input(
    "Ask ALBA a question or continue the conversation…",
    key="alba_chat_prompt",
    max_chars=available_chars,
    disabled=not (account and api_key),
)

if prompt:
    st.session_state["alba_pending_chat_text"] = prompt + doc_context
    st.session_state["alba_pending_display_question"] = prompt
    st.session_state["alba_pending_chat_error"] = None

pending = st.session_state.get("alba_pending_chat_text")
error = st.session_state.get("alba_pending_chat_error")
retry = False
if pending and error:
    with st.chat_message("user"):
        _render_chat_content(pending)
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
                _render_chat_content(pending)
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
                    title = st.session_state.get(
                        "alba_pending_display_question", pending
                    ).strip().replace("\n", " ")[:75][:75]
                    active_id = store.create_conversation(
                        owner, mode=mode, project_id=new_project,
                        title=title,
                    )
                store.append_exchange(owner, active_id, pending, reply)
                st.session_state["alba_active_conversation"] = active_id
                st.session_state["alba_pending_chat_text"] = None
                st.session_state["alba_pending_chat_error"] = None
                st.session_state["alba_pending_display_question"] = None
                st.session_state["alba_doc_nonce"] = (
                    st.session_state.get("alba_doc_nonce", 0) + 1
                )
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
