"""ALBA Chat Workspace: projects, saved threads and multi-turn continuation.

Cloud-deployed persistent history is available ONLY after verified OIDC
sign-in and external PostgreSQL configuration. Otherwise the clearly labeled
demo runs in per-browser-session SQLite memory and is lost on session restart.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO
from uuid import uuid4

from docx import Document

import streamlit as st

from chat_backend import (
    ANSWER_STYLES, SUPPORTED_JURISDICTIONS,
    MAX_USER_CHARS, generate_chat_reply, prepare_chat_messages,
)
from guest_browser_storage import (
    initialize_browser_history, save_browser_history,
    export_guest_workspace, restore_guest_workspace,
    validate_guest_workspace,
)
from chat_history_status import chat_history_status
from chat_backup import backup_bytes, parse_backup_file
from chat_store import ChatStore, MODES, MAX_CHAT_TITLE
from chat_auth import verified_chat_owner
from alba_workspace_ui import apply_workspace_ui
from privacy_guard import BLOCK_NOTICE, scan_text_fields, screen_upload, upload_block_message
from ui_theme import apply_theme
from workspace_sources import user_source_links, user_document_excerpts
from alba_followups import follow_up_questions
from official_research import official_links
from legal_sources_probe import probe_case

st.set_page_config(page_title="ALBA | European Legal Workspace", page_icon="⚖️", layout="wide")
# The chat is independently styled below; other tools retain their own theme.
# The shared workspace hero remains; omit duplicate page-level title.

# ChatGPT-like layout: a centered empty-state composer and a docked composer
# for ongoing conversations. The native Streamlit attachment + lives inside it.
apply_workspace_ui()


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
previous_scope = st.session_state.get("alba_scope")
if previous_scope != scope:
    st.session_state["alba_scope"] = scope
    # Session state may survive a login/logout transition. Never carry a
    # different owner's draft question, active conversation or project into
    # the newly selected account/storage scope.
    for key in (
        "alba_active_conversation", "alba_new_chat_project",
        "alba_pending_chat_text", "alba_pending_display_question",
        "alba_pending_chat_error", "alba_chat_submit_staged",
        "alba_browser_confirm_pending", "alba_browser_confirm_exchange",
    ):
        st.session_state.pop(key, None)
    if previous_scope and previous_scope.startswith("account:") and not persistent:
        # A returning guest must re-read their browser snapshot rather than
        # accidentally relying on a stale, account-era in-memory workspace.
        st.session_state.pop("alba_browser_ready", None)
        st.session_state.pop("alba_browser_available", None)
        st.session_state.pop("alba_browser_error", None)
        old_demo = st.session_state.pop("alba_demo_store", None)
        if old_demo is not None:
            old_demo.close()
        st.session_state.pop("alba_demo_owner", None)
        st.rerun()

if not persistent:
    initialize_browser_history(store, owner)
    # Keep the component at the same position in EVERY rerun. Save new
    # messages, project changes and unfinished questions immediately.
    browser_saved = save_browser_history(
        store, owner,
        active_id=st.session_state.get("alba_active_conversation"),
        pending_text=st.session_state.get("alba_pending_chat_text"),
        pending_project_id=st.session_state.get("alba_new_chat_project"),
    )
    # Successful saves are silent; storage failures remain visible below.
    if st.session_state.get("alba_browser_error"):
        st.warning(st.session_state["alba_browser_error"])
    if st.session_state.get("alba_browser_confirm_pending"):
        if st.session_state.get("alba_browser_available") and not browser_saved:
            st.caption("Saving your question in this browser…")
            if st.button(
                "Continue without confirmed saving",
                key="alba_skip_draft_save",
            ):
                st.session_state["alba_browser_confirm_pending"] = False
            else:
                # Do not send a newly submitted prompt to Cloudflare until
                # localStorage has acknowledged the exact pending revision.
                st.stop()
        else:
            st.session_state["alba_browser_confirm_pending"] = False
    if st.session_state.get("alba_browser_confirm_exchange"):
        if st.session_state.get("alba_browser_available") and not browser_saved:
            st.caption("Saving the conversation in this browser…")
            if st.button(
                "Continue without confirmed conversation saving",
                key="alba_skip_exchange_save",
            ):
                st.session_state["alba_browser_confirm_exchange"] = False
            else:
                st.stop()
        else:
            st.session_state["alba_browser_confirm_exchange"] = False


# Never imply that sign-in alone provides cloud persistence. The account
# route requires BOTH a configured OIDC provider and a PostgreSQL database.
if _oidc_configured() and _secret("ALBA_DATABASE_URL"):
    with st.sidebar:
        if _verified_owner():
            if st.button("Log out", key="alba_logout"):
                st.logout()
        elif st.button("Sign in to save conversations", key="alba_login"):
            st.login()

def _open_conversation(chat_id: str) -> None:
    st.session_state["alba_active_conversation"] = chat_id
    st.session_state["alba_new_chat_project"] = None
    st.session_state["alba_pending_chat_text"] = None
    st.session_state["alba_pending_chat_error"] = None
    st.session_state.pop("alba_pending_attachment", None)


def _start_chat(project_id: str | None = None) -> None:
    st.session_state["alba_active_conversation"] = None
    st.session_state["alba_new_chat_project"] = project_id
    st.session_state["alba_pending_chat_text"] = None
    st.session_state["alba_pending_chat_error"] = None
    st.session_state.pop("alba_pending_attachment", None)


def _mark_history_changed() -> None:
    """Require confirmation that every guest mutation reaches the browser."""
    if not persistent:
        st.session_state["alba_browser_confirm_exchange"] = True


def _sidebar_chat_entry(chat: dict, available_projects: list[dict]) -> None:
    """One-click open, plus compact rename and move controls for each chat."""
    open_col, menu_col = st.columns([5, 1], vertical_alignment="center", gap="small")
    with open_col:
        if st.button(
            chat["title"][:58],
            key="alba_open_" + chat["id"],
            type=(
                "primary" if chat["id"] ==
                st.session_state.get("alba_active_conversation")
                else "secondary"
            ),
            use_container_width=True,
        ):
            _open_conversation(chat["id"])
            st.rerun()
    with menu_col:
        with st.popover("⋯", help="Rename chat or move to project"):
            renamed = st.text_input(
                "Rename chat", value=chat["title"],
                max_chars=MAX_CHAT_TITLE,
                key="alba_sidebar_chat_name_" + chat["id"],
            )
            if st.button("Save chat name", key="alba_sidebar_save_name_" + chat["id"]):
                try:
                    changed = store.rename_conversation(owner, chat["id"], renamed)
                except ValueError:
                    st.error("Enter a valid public chat name.")
                else:
                    if changed:
                        _mark_history_changed()
                        st.rerun()
                    st.error("Chat is no longer available.")

            choices = [None] + [project["id"] for project in available_projects]
            names = {project["id"]: project["name"] for project in available_projects}
            target = st.selectbox(
                "Move to project", choices,
                index=choices.index(chat["project_id"])
                if chat["project_id"] in choices else 0,
                format_func=lambda item: (
                    names.get(item, "Project") if item is not None else "No project"
                ),
                key="alba_sidebar_move_target_" + chat["id"],
            )
            if st.button(
                "Move chat",
                key="alba_sidebar_move_chat_" + chat["id"],
                disabled=target == chat["project_id"],
            ):
                try:
                    moved = store.set_conversation_project(owner, chat["id"], target)
                except ValueError:
                    st.error("This project is not available.")
                else:
                    if moved:
                        _mark_history_changed()
                        st.rerun()
                    st.error("Chat is no longer available.")


with st.sidebar:
    if st.button("New chat", key="alba_new_chat", icon=":material/add:", use_container_width=True):
        _start_chat()
        st.rerun()

    # Search filters only the displayed conversation list. All chats and
    # projects remain in the owner-scoped store; no data are discarded.
    search_text = st.text_input(
        "Search conversations",
        key="alba_sidebar_chat_search",
        placeholder="Search chats…",
        label_visibility="collapsed",
    ).strip().casefold()

    projects = store.list_projects(owner)
    conversations = store.list_conversations(owner)
    chats_by_project = {item["id"]: [] for item in projects}
    unassigned_chats = []
    project_names = {item["id"]: item["name"].casefold() for item in projects}
    for chat in conversations:
        if search_text and not (
            search_text in chat["title"].casefold()
            or search_text in project_names.get(chat["project_id"], "")
        ):
            continue
        if chat["project_id"] in chats_by_project:
            chats_by_project[chat["project_id"]].append(chat)
        else:
            unassigned_chats.append(chat)

    heading, add_project = st.columns([3, 1], vertical_alignment="center")
    with heading:
        st.subheader("Projects")
    with add_project:
        with st.popover("＋", help="Create a project"):
            project_name = st.text_input(
                "Project name", max_chars=75, key="alba_sidebar_project_name"
            )
            if st.button("Create project", key="alba_sidebar_create_project"):
                try:
                    created = store.create_project(owner, project_name)
                except ValueError:
                    st.error("Enter a valid project name.")
                else:
                    _start_chat(created)
                    _mark_history_changed()
                    st.rerun()

    for project in projects:
        related = chats_by_project[project["id"]]
        if search_text and not related and search_text not in project["name"].casefold():
            continue
        with st.expander(
            "📁 " + project["name"] + " (" + str(len(related)) + ")",
            expanded=(
                project["id"] == st.session_state.get("alba_new_chat_project")
                or any(
                    chat["id"] == st.session_state.get("alba_active_conversation")
                    for chat in related
                )
            ),
        ):
            project_action, project_options = st.columns(
                [5, 1], vertical_alignment="center", gap="small"
            )
            with project_action:
                if st.button(
                    "＋ New chat in project",
                    key="alba_project_new_" + project["id"],
                    use_container_width=True,
                ):
                    _start_chat(project["id"])
                    st.rerun()
            with project_options:
                with st.popover("⋯", help="Rename project"):
                    project_name = st.text_input(
                        "Rename project", value=project["name"],
                        max_chars=75, key="alba_project_rename_" + project["id"],
                    )
                    if st.button(
                        "Save project name",
                        key="alba_project_save_name_" + project["id"],
                    ):
                        try:
                            changed = store.rename_project(owner, project["id"], project_name)
                        except ValueError:
                            st.error("Enter a valid public project name.")
                        else:
                            if changed:
                                _mark_history_changed()
                                st.rerun()
                            st.error("Project is no longer available.")
            for chat in related[:50]:
                _sidebar_chat_entry(chat, projects)

    st.subheader("Chats")
    if search_text and not unassigned_chats and not any(chats_by_project.values()):
        st.caption("No conversations match your search.")
    for chat in unassigned_chats[:50]:
        _sidebar_chat_entry(chat, projects)

# Keep backup and recovery under one optional menu rather than adding
# controls throughout the ChatGPT-style sidebar.
with st.sidebar:
    with st.popover("Backup & restore", icon=":material/history:"):
        try:
            workspace_json = export_guest_workspace(
                store, owner,
                active_id=st.session_state.get("alba_active_conversation"),
                pending_text=st.session_state.get("alba_pending_chat_text"),
                pending_project_id=st.session_state.get("alba_new_chat_project"),
            )
        except ValueError:
            st.caption(
                "Full workspace backup unavailable at the current size. "
                "Download important conversations individually."
            )
        else:
            st.download_button(
                "Download all chats and projects (.json)",
                data=workspace_json.encode("utf-8"),
                file_name="ALBA_workspace_backup.json",
                mime="application/json",
                key="alba_download_workspace",
                use_container_width=True,
            )

        restore_file = st.file_uploader(
            "Import a conversation backup (.json)",
            type=["json"],
            key="alba_restore_single_file",
        )
        if restore_file is not None and st.button(
            "Restore conversation", key="alba_restore_single",
        ):
            try:
                backup = parse_backup_file(restore_file.getvalue())
                restored = store.import_conversation_backup(owner, backup)
            except ValueError as exc:
                st.error(str(exc))
            else:
                _open_conversation(restored)
                _mark_history_changed()
                st.rerun()

        if not persistent:
            workspace_file = st.file_uploader(
                "Import a full workspace backup (.json) into an empty workspace",
                type=["json"],
                key="alba_restore_workspace_file",
            )
            if workspace_file is not None and st.button(
                "Restore full workspace", key="alba_restore_workspace",
            ):
                if store.list_conversations(owner) or store.list_projects(owner):
                    st.error(
                        "Full workspace restoration requires an empty workspace. "
                        "Existing chats will not be overwritten."
                    )
                else:
                    try:
                        raw = workspace_file.getvalue().decode("utf-8-sig")
                        clean = validate_guest_workspace(raw)
                        recovered = restore_guest_workspace(store, owner, raw)
                    except (ValueError, UnicodeError) as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["alba_active_conversation"] = recovered
                        st.session_state["alba_pending_chat_text"] = clean["pending"]
                        st.session_state["alba_pending_display_question"] = (
                            clean["pending"].split(
                                "\n\n[PUBLIC DOCUMENT EXCERPT:", 1
                            )[0] if clean["pending"] else None
                        )
                        st.session_state["alba_pending_chat_error"] = (
                            "This question was not answered. Select Retry to continue."
                            if clean["pending"] else None
                        )
                        project_index = clean["pending_project"]
                        st.session_state["alba_new_chat_project"] = (
                            store.list_projects(owner)[project_index]["id"]
                            if project_index is not None else None
                        )
                        _mark_history_changed()
                        st.rerun()


active_id = st.session_state.get("alba_active_conversation")
conversation = (
    store.get_conversation(owner, active_id) if active_id else None
)
if active_id and conversation is None:
    st.session_state["alba_active_conversation"] = None
    active_id = None

def _response_docx(answer: str) -> bytes:
    """Editable, lightweight Word export for one legal research answer."""
    document = Document()
    for raw in answer.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            document.add_heading(line[4:], level=3)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            document.add_heading(line[2:], level=1)
        elif line.startswith(("- ", "* ")):
            document.add_paragraph(line[2:], style="List Bullet")
        else:
            document.add_paragraph(line)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _response_actions(message: dict, response_no: int, chat_id: str) -> None:
    """Copy/Word/Save actions next to a saved answer, without modifying chat."""
    identity = f"{chat_id}_{response_no}"
    stamp = message.get("created_at", "")
    try:
        date_label = datetime.fromisoformat(stamp.replace("Z", "+00:00")).strftime(
            "%d.%m.%Y · %H:%M"
        )
    except (ValueError, TypeError, AttributeError):
        date_label = ""
    when, copy, word, save = st.columns(
        [2.2, 1, 1, 1], gap="small", vertical_alignment="center"
    )
    with when:
        st.caption(date_label)
    with copy:
        with st.popover("Copy", icon=":material/content_copy:"):
            st.caption("Copy the full text using the icon in this box.")
            st.code(message["content"], language=None)
    with word:
        st.download_button(
            "Word",
            data=_response_docx(message["content"]),
            file_name=f"ALBA_response_{response_no}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="alba_word_" + identity,
            on_click="ignore",
        )
    with save:
        st.download_button(
            "Save",
            data=message["content"],
            file_name=f"ALBA_response_{response_no}.md",
            mime="text/markdown",
            key="alba_save_" + identity,
            on_click="ignore",
        )


def _render_chat_content(value: str) -> None:
    marker = "\n\n[PUBLIC DOCUMENT EXCERPT: "
    if marker not in value:
        st.markdown(value)
        return
    question, raw_source = value.split(marker, 1)
    st.markdown(question)
    with st.expander("Attached public document excerpt"):
        st.code(raw_source, language=None)


# Chat-first layout. The optional sources panel never claims that the
# chat model retrieved or verified an official text: only user-shared
# references are listed until a verified research connector is wired in.
header_left, header_right = st.columns([5, 1], vertical_alignment="center")
with header_left:
    st.markdown(
        '<div class="alba-top-title">ALBA'
        '<span class="alba-top-subtitle">European & Albanian legal workspace</span>'
        '</div>',
        unsafe_allow_html=True,
    )
with header_right:
    if st.button(
        "Sources", key="alba_sources_toggle", icon=":material/bookmarks:",
        use_container_width=True,
        help="Open the official references and document excerpts for this chat",
    ):
        st.session_state["alba_sources_open"] = not st.session_state.get(
            "alba_sources_open", True
        )
        st.rerun()

show_sources = bool(st.session_state.get("alba_sources_open", False))
if show_sources:
    chat_area, sources_area = st.columns([3.1, 1], gap="large")
else:
    chat_area = st.container()

with chat_area:
    if conversation:
        mode = conversation["mode"]
        messages = store.list_messages(owner, active_id)

        chat_heading, chat_actions = st.columns([12, 1], vertical_alignment="center")
        with chat_heading:
            st.caption(conversation["title"])
        with chat_actions:
            with st.popover("⋯", help="Chat options: rename, move, export or delete"):
                new_title = st.text_input(
                    "Conversation title",
                    value=conversation["title"],
                    key="alba_rename_title_" + active_id,
                    max_chars=MAX_CHAT_TITLE,
                )
                if st.button("Save title", key="alba_save_title_" + active_id):
                    try:
                        updated = store.rename_conversation(owner, active_id, new_title)
                    except ValueError:
                        st.error("Please enter a valid, public conversation title.")
                    except Exception:
                        st.error("Could not rename the conversation. Try again.")
                    else:
                        if updated:
                            _mark_history_changed()
                            st.rerun()
                        st.error("The conversation is no longer available.")
        
                try:
                    portable_chat = backup_bytes(conversation, messages)
                except ValueError:
                    st.caption(
                        "This conversation exceeds the single-chat backup limit. "
                        "Try the full workspace backup."
                    )
                else:
                    st.download_button(
                        "Export conversation (.json)",
                        data=portable_chat,
                        file_name="ALBA_chat_" + active_id[:12] + ".json",
                        mime="application/json",
                        key="alba_export_chat_" + active_id,
                        use_container_width=True,
                    )
        
                confirmed = st.checkbox(
                    "I confirm permanent deletion",
                    value=False,
                    key="alba_delete_confirm_" + active_id,
                )
                if st.button(
                    "Delete conversation",
                    key="alba_delete_chat_" + active_id,
                    disabled=not confirmed,
                ):
                    try:
                        deleted = store.delete_conversation(owner, active_id)
                    except Exception:
                        st.error("Could not delete the conversation. Try again.")
                    else:
                        if deleted:
                            _start_chat()
                            _mark_history_changed()
                            st.rerun()
                        st.error("The conversation is no longer available.")

                st.divider()
                st.caption("Project")
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
                            _mark_history_changed()
                            st.rerun()
                        except ValueError:
                            st.error("Enter a valid project name.")
                elif target != conversation["project_id"]:
                    if st.button("Move", key="alba_move_" + active_id):
                        store.set_conversation_project(owner, active_id, target)
                        _mark_history_changed()
                        st.rerun()
        

        response_no = 0
        for message in messages:
            with st.chat_message(message["role"]):
                _render_chat_content(message["content"])
                if message["role"] == "assistant":
                    response_no += 1
                    _response_actions(message, response_no, active_id)

        # Stay in this conversation for drafting, analysis and reporting.
        # Other specialist implementations remain registered but hidden.
        latest_question = next(
            (item["content"] for item in reversed(messages)
             if item["role"] == "user"),
            "",
        )

        # Three relevant Albanian/EU-law questions beneath the latest answer.
        # They are generated locally from the last user question: no extra
        # model requests, invented legal claims or citation placeholders.
        if messages and messages[-1]["role"] == "assistant":
            followups = follow_up_questions(latest_question, messages[-1]["content"])
            if followups:
                with st.container(key="alba_followups"):
                    for idx, suggestion in enumerate(followups):
                        if st.button(
                            suggestion,
                            key=f"alba_followup_{active_id}_{len(messages)}_{idx}",
                        ):
                            st.session_state["alba_pending_chat_text"] = suggestion
                            st.session_state["alba_pending_display_question"] = suggestion
                            st.session_state["alba_pending_chat_error"] = None
                            st.session_state["alba_chat_submit_staged"] = True
                            if not persistent:
                                st.session_state["alba_browser_confirm_pending"] = True
                            st.rerun()
    else:
        mode = "general"
        messages = []
    if not conversation:
        st.markdown(
            '<div class="alba-welcome-eyebrow">ALBA LEGAL WORKSPACE</div>'
            '<div class="alba-welcome-title">What would you like to work on?</div>'
            '<div class="alba-welcome-subtitle">'
            'Research EU and Albanian law, compare legal texts, '
            'review a public document or draft institutional material. '
            'Start with a question below.'
            '</div>',
            unsafe_allow_html=True,
        )

if show_sources:
    with sources_area:
        with st.container(key="alba_sources_panel"):
            st.markdown(
                '<div class="alba-source-title">SOURCES & CITATIONS</div>',
                unsafe_allow_html=True,
            )
            answer_positions = [
                idx for idx, item in enumerate(messages)
                if item.get("role") == "assistant"
            ]
            if answer_positions:
                selected_response = st.selectbox(
                    "Response",
                    list(range(1, len(answer_positions) + 1)),
                    index=len(answer_positions) - 1,
                    key="alba_selected_response",
                    format_func=lambda value: f"RESPONSE {value}",
                )
                response_end = answer_positions[selected_response - 1] + 1
                response_start = (
                    answer_positions[selected_response - 2] + 1
                    if selected_response > 1 else 0
                )
                relevant_messages = messages[response_start:response_end]
            else:
                st.caption("No response to cite yet.")
                relevant_messages = messages
            source_tab, document_tab = st.tabs(["Official sources", "Documents"])
            with source_tab:
                st.caption(
                    "Official links you shared. Their content, status and "
                    "consolidated versions have not yet been independently verified "
                    "by this chat. These are references, not confirmed citations."
                )
                cited_links = user_source_links(relevant_messages)
                st.caption(f"{len(cited_links)} user-provided reference(s)")
                if cited_links:
                    for index, source in enumerate(cited_links, start=1):
                        source_number, source_link = st.columns(
                            [1, 8], gap="small", vertical_alignment="center"
                        )
                        with source_number:
                            st.markdown(f"**{index}**")
                        with source_link:
                            st.link_button(
                                source["label"], source["url"],
                                use_container_width=True,
                            )
                else:
                    st.caption("No official document links in this conversation.")
                # Current response source navigation: direct CELEX links,
                # EUR-Lex NIM comparisons, and exact known QBZ references.
                current_question = next((
                    item["content"] for item in reversed(relevant_messages)
                    if item.get("role") == "user"
                ), "")
                current_sources = official_links(current_question, relevant_messages)
                if current_sources:
                    st.divider()
                    st.markdown("**Links to official legal sources**")
                    st.caption(
                        "These are navigational links; they are not verified "
                        "citations to a read legal provision."
                    )
                    for i, candidate in enumerate(current_sources):
                        st.link_button(
                            candidate.label, candidate.url,
                            use_container_width=True,
                        )
                        st.caption(candidate.note)
                        if candidate.scope in {"known_act", "official_eu_act"}:
                            if st.button(
                                "Check online source metadata",
                                key=f"alba_probe_{selected_response if answer_positions else 0}_{i}",
                            ):
                                try:
                                    from urllib.parse import quote
                                    exact_url = candidate.url.replace(
                                        "uri=CELEX:", "uri=CELEX%3A"
                                    )
                                    outcome = probe_case({
                                        "id": "chat-source",
                                        "jurisdiction": (
                                            "AL" if candidate.scope == "known_act"
                                            else "EU"
                                        ),
                                        "url": exact_url,
                                    })
                                    st.info(
                                        "Official source check: "
                                        + outcome.outcome
                                        + " · identity observed: "
                                        + ("yes" if outcome.identity_observed else "no")
                                        + ". " + outcome.details
                                        + " This does not certify the consolidated "
                                        "text or status in force."
                                    )
                                except (ValueError, OSError) as exc:
                                    st.warning(
                                        "Could not check the official source: "
                                        + str(exc)[:150]
                                    )
                st.divider()
                st.caption("Open official registers")
                st.link_button(
                    "QBZ", "https://qbz.gov.al/", use_container_width=True,
                )
                st.link_button(
                    "EUR-Lex", "https://eur-lex.europa.eu/",
                    use_container_width=True,
                )
            with document_tab:
                document_names = user_document_excerpts(messages)
                if document_names:
                    for name in document_names:
                        st.markdown("📄 " + name)
                    st.caption(
                        "These are excerpts attached to this conversation, "
                        "not an indexed document library."
                    )
                else:
                    st.caption(
                        "Public documents attached using + appear here after "
                        "their excerpts are added to the conversation."
                    )

# Use Streamlit's native attachment '+' rather than a separate popover.
# A new chat is isolated: only this conversation's own messages are passed
# to the model. Changing project or creating a new chat never links histories.
account, api_key = (
    _secret("CLOUDFLARE_ACCOUNT_ID"), _secret("CLOUDFLARE_API_TOKEN"),
)
if not account or not api_key:
    st.error(
        "AI chat is not configured. Check CLOUDFLARE_ACCOUNT_ID and "
        "CLOUDFLARE_API_TOKEN in Streamlit Cloud → App settings → Secrets."
    )

def _document_context(name: str, excerpt: str) -> str:
    return (
        "\n\n[PUBLIC DOCUMENT EXCERPT: " + name + "]\n"
        + excerpt + "\n[/PUBLIC DOCUMENT EXCERPT]"
    )

# Long files must be deliberately excerpted: no silent 3,200-character cut.
pending_attachment = st.session_state.get("alba_pending_attachment")
if pending_attachment:
    st.info(
        "The attached document is long. Select the public passage you want "
        "to use in this conversation (up to 3,200 characters)."
    )
    excerpt = st.text_area(
        "Document excerpt", value=pending_attachment["text"][:3200],
        max_chars=3200, height=180,
        key="alba_pending_attachment_excerpt",
    )
    selection, cancel = st.columns([1, 1])
    with selection:
        if st.button("Use selected excerpt", key="alba_confirm_attachment"):
            if not excerpt.strip() or scan_text_fields(
                excerpt, public_legal=True
            ).blocked:
                st.error("Select a valid public passage.")
            else:
                question = pending_attachment["question"]
                content = question + _document_context(
                    pending_attachment["name"], excerpt.strip(),
                )
                if len(content) > MAX_USER_CHARS:
                    st.error("The message is too long; shorten the excerpt.")
                else:
                    st.session_state["alba_pending_chat_text"] = content
                    st.session_state["alba_pending_display_question"] = question
                    st.session_state["alba_pending_chat_error"] = None
                    st.session_state["alba_chat_submit_staged"] = True
                    if not persistent:
                        st.session_state["alba_browser_confirm_pending"] = True
                    st.session_state.pop("alba_pending_attachment", None)
                    st.rerun()
    with cancel:
        if st.button("Cancel attachment", key="alba_cancel_attachment"):
            st.session_state.pop("alba_pending_attachment", None)
            st.rerun()

# Controls modelled on the reference UI. The selected style and country
# actually modify the system guidance used for the next answer.
_JURISDICTION_FLAGS = {
    "European Union": "🇪🇺", "Albania": "🇦🇱", "Germany": "🇩🇪",
    "France": "🇫🇷", "Italy": "🇮🇹", "Spain": "🇪🇸",
    "Greece": "🇬🇷", "Kosovo": "🇽🇰", "North Macedonia": "🇲🇰",
    "Montenegro": "🇲🇪", "Serbia": "🇷🇸",
    "Bosnia and Herzegovina": "🇧🇦", "Croatia": "🇭🇷",
    "Netherlands": "🇳🇱", "Poland": "🇵🇱", "Denmark": "🇩🇰",
    "Finland": "🇫🇮", "Sweden": "🇸🇪", "Norway": "🇳🇴",
}


def _chat_composer_controls() -> None:
    current_style = st.session_state.get("alba_answer_style", "Lawyer")
    selected = st.session_state.get("alba_jurisdictions", ["European Union"])
    current_country = (
        _JURISDICTION_FLAGS.get(selected[0], "🌐") if selected else "🌐"
    )
    plus_col, country_col, project_col = st.columns(
        [1.45, 1.4, 1.15], gap="small", vertical_alignment="center",
    )
    with plus_col:
        with st.popover("Style · " + current_style, help="Choose the answer format"):
            st.selectbox(
                "Answer style", options=list(ANSWER_STYLES),
                key="alba_answer_style",
                help="Changes the drafting approach of the next reply.",
            )
            st.caption("Attach a public document using + inside the chat box.")
    with country_col:
        with st.popover("Country · " + current_country, icon=":material/public:"):
            st.multiselect(
                "Jurisdictions", options=list(SUPPORTED_JURISDICTIONS),
                default=["European Union"],
                key="alba_jurisdictions",
                max_selections=6,
                format_func=lambda name: _JURISDICTION_FLAGS.get(name, "🌐") + " " + name,
                help="Sets research scope only; it does not establish access to official texts.",
            )
            st.caption("Selected countries guide the answer. No live document count is claimed.")
    with project_col:
        with st.popover("Project", icon=":material/create_new_folder:"):
            st.caption("Create a project and start a chat within it.")
            new_project = st.text_input(
                "Project name", max_chars=75, key="alba_composer_project_name",
            )
            if st.button(
                "+ New project", key="alba_composer_create_project",
                disabled=not new_project.strip(),
            ):
                try:
                    new_id = store.create_project(owner, new_project)
                except ValueError:
                    st.error("Enter a valid project name.")
                else:
                    _start_chat(new_id)
                    _mark_history_changed()
                    st.rerun()


# A blank chat gets a centered input. Once it has messages, the very same
# native chat widget is placed at root level and Streamlit docks it below.
chat_input_options = dict(
    key="alba_chat_prompt",
    max_chars=MAX_USER_CHARS,
    accept_file=True,
    file_type=["docx", "xlsx", "pdf", "pptx"],
    max_upload_size=12,
    disabled=not (account and api_key) or bool(pending_attachment),
)
if conversation:
    _chat_composer_controls()
    submission = st.chat_input(
        "Message…", **chat_input_options,
    )
else:
    with st.container(key="alba_chat_empty"):
        _chat_composer_controls()
        submission = st.chat_input(
            "Message…", **chat_input_options,
        )

prompt = None
doc_context = ""
if submission:
    question = (
        submission.strip() if isinstance(submission, str)
        else (submission.text or "").strip()
    )
    # Streamlit's native + attaches a file to the very same chat submission.
    # No separate uploader or temporary upload state is required.
    uploads = list(submission.files) if not isinstance(submission, str) else []
    if uploads:
        # Validate both file size and contents before any AI request.
        document = uploads[0]
        if len(document.getvalue()) > 12 * 1024 * 1024:
            st.error("The uploaded file exceeds the 12 MB limit.")
            st.stop()
        checked = screen_upload(
            document.name, document.getvalue(),
            public_legal=True, max_chars=150000,
        )
        if checked.blocked:
            st.error(upload_block_message(checked.reason))
        else:
            question = question or "Review the attached public document."
            if checked.warning:
                st.warning(checked.warning)
            if len(checked.text) > 3200:
                st.session_state["alba_pending_attachment"] = {
                    "name": document.name,
                    "text": checked.text,
                    "question": question,
                }
                st.rerun()
            else:
                doc_context = _document_context(document.name, checked.text)
                if len(question + doc_context) > MAX_USER_CHARS:
                    st.error("The question and attachment exceed the chat limit.")
                else:
                    prompt = question
    else:
        prompt = question or None

if prompt:
    st.session_state["alba_pending_chat_text"] = prompt + doc_context
    st.session_state["alba_pending_display_question"] = prompt
    st.session_state["alba_pending_chat_error"] = None
    if not persistent and not scan_text_fields(
        st.session_state["alba_pending_chat_text"], public_legal=True
    ).blocked:
        # Stage the question, rerun, and wait for the browser to verify
        # its save before making the (potentially long) AI request.
        st.session_state["alba_chat_submit_staged"] = True
        st.session_state["alba_browser_confirm_pending"] = True
        st.rerun()

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

staged_submission = bool(
    st.session_state.pop("alba_chat_submit_staged", False)
)
if (prompt or retry or staged_submission) and pending:
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
                mode=mode, history=messages, user_text=pending,
                answer_style=st.session_state.get("alba_answer_style", "Lawyer"),
                jurisdictions=st.session_state.get("alba_jurisdictions", ["European Union"]),
            )
            with st.chat_message("assistant"):
                with st.spinner("ALBA is responding..."):
                    reply = generate_chat_reply(
                        mode=mode, history=messages, user_text=pending,
                        account_id=account, api_token=api_key,
                        answer_style=st.session_state.get("alba_answer_style", "Lawyer"),
                        jurisdictions=st.session_state.get("alba_jurisdictions", ["European Union"]),
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
                        owner, mode=mode,
                        project_id=st.session_state.get("alba_new_chat_project"),
                        title=title,
                    )
                store.append_exchange(owner, active_id, pending, reply)
                if not persistent:
                    st.session_state["alba_browser_confirm_exchange"] = True
                st.session_state["alba_active_conversation"] = active_id
                st.session_state["alba_new_chat_project"] = None
                st.session_state["alba_pending_chat_text"] = None
                st.session_state["alba_pending_chat_error"] = None
                st.session_state["alba_pending_display_question"] = None
                st.rerun()
            except Exception:
                st.session_state["alba_pending_chat_error"] = (
                    "The AI responded, but saving the conversation failed. "
                    "Use the visible response below and retry after fixing storage."
                )
                st.error(st.session_state["alba_pending_chat_error"])
                with st.chat_message("assistant"):
                    st.markdown(reply)

