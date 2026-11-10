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
from guest_browser_storage import (
    initialize_browser_history, save_browser_history,
)
from chat_store import ChatStore, MODES
from chat_auth import verified_chat_owner
from chat_handoff import suggest_handoff, prepare_handoff
from privacy_guard import BLOCK_NOTICE, scan_text_fields, screen_upload, upload_block_message
from ui_theme import apply_theme

st.set_page_config(page_title="ALBA | Chat Workspace", page_icon="💬", layout="wide")
apply_theme("WORKSPACE")
st.title("ALBA")


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

if not persistent and not st.session_state.get("alba_browser_available"):
    st.warning("Browser saving unavailable. Your chats may not persist.")

if _oidc_configured():
    with st.sidebar:
        if _verified_owner():
            if st.button("Log out", key="alba_logout"):
                st.logout()
        elif st.button("Sign in to save conversations", key="alba_login"):
            st.login()

with st.sidebar:
    if st.button("＋ New chat", key="alba_new_chat", use_container_width=True):
        st.session_state["alba_active_conversation"] = None
        st.session_state["alba_pending_chat_text"] = None
        st.session_state["alba_pending_chat_error"] = None
        st.rerun()

    st.subheader("Chats")
    conversations = store.list_conversations(owner)
    for chat in conversations[:45]:
        current = chat["id"] == st.session_state["alba_active_conversation"]
        if st.button(
            chat["title"][:65],
            key="alba_open_" + chat["id"],
            use_container_width=True,
            type="primary" if current else "secondary",
        ):
            st.session_state["alba_active_conversation"] = chat["id"]
            st.session_state["alba_pending_chat_text"] = None
            st.session_state["alba_pending_chat_error"] = None
            st.rerun()

active_id = st.session_state.get("alba_active_conversation")
conversation = (
    store.get_conversation(owner, active_id) if active_id else None
)
if active_id and conversation is None:
    st.session_state["alba_active_conversation"] = None
    active_id = None

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
    mode = conversation["mode"]
    with st.popover("Move to project", icon=":material/folder_open:"):
        projects = store.list_projects(owner)
        names = {item["id"]: item["name"] for item in projects}
        choices = [None] + [item["id"] for item in projects] + ["__new__"]
        project_index = (
            choices.index(conversation["project_id"])
            if conversation["project_id"] in choices else 0
        )
        target = st.selectbox(
            "Project", choices, index=project_index,
            format_func=lambda item: (
                "Create new project" if item == "__new__"
                else ("No project" if item is None else names.get(item, "Project"))
            ),
            key="alba_project_target_" + active_id,
        )
        if target == "__new__":
            new_name = st.text_input(
                "Project name", key="alba_new_project_name_" + active_id,
                max_chars=75,
            )
            if st.button("Create and move", key="alba_create_move_" + active_id):
                try:
                    created = store.create_project(owner, new_name)
                    store.set_conversation_project(owner, active_id, created)
                    st.rerun()
                except ValueError:
                    st.error("Enter a valid project name.")
        elif target != conversation["project_id"]:
            if st.button("Move", key="alba_move_" + active_id):
                store.set_conversation_project(owner, active_id, target)
                st.rerun()

    messages = store.list_messages(owner, active_id)
    for message in messages:
        with st.chat_message(message["role"]):
            _render_chat_content(message["content"])

    # If the last user turn requests a specialised ALBA workflow, offer
    # exactly one direct handoff. General questions stay in the conversation.
    latest_question = next(
        (item["content"] for item in reversed(messages)
         if item["role"] == "user"),
        "",
    )
    recommended = suggest_handoff(latest_question)
    if recommended and st.button(
        "Continue in " + recommended.label,
        key="alba_handoff_" + active_id + "_" + str(len(messages)),
    ):
        prepare_handoff(recommended, latest_question, st.session_state)
        st.switch_page(recommended.page)
else:
    st.subheader("How can I help?")
    mode = "general"
    messages = []

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
                        owner, mode=mode, project_id=None,
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
