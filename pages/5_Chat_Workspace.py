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
    export_guest_workspace, restore_guest_workspace,
    validate_guest_workspace,
)
from chat_history_status import chat_history_status
from chat_backup import backup_bytes, parse_backup_file
from chat_store import ChatStore, MODES, MAX_CHAT_TITLE
from chat_auth import verified_chat_owner
from chat_handoff import suggest_handoff, prepare_handoff
from privacy_guard import BLOCK_NOTICE, scan_text_fields, screen_upload, upload_block_message
from ui_theme import apply_theme
from workspace_sources import user_source_links, user_document_excerpts

st.set_page_config(page_title="ALBA | Chat Workspace", page_icon="💬", layout="wide")
apply_theme("WORKSPACE")
# The shared workspace hero remains; omit duplicate page-level title.

# ChatGPT-like layout: a centered empty-state composer and a docked composer
# for ongoing conversations. The native Streamlit attachment + lives inside it.
st.markdown(
    """
    <style>
    /* The application-wide decorative hero is not a chat message. */
    .alba-hero {display: none !important;}
    [data-testid="stMainBlockContainer"] {
        max-width: 1040px;
        padding-top: 1.25rem;
        padding-bottom: 9rem;
    }
    .st-key-alba_chat_empty {
        max-width: 760px;
        width: 100%;
        margin: clamp(80px, 20vh, 210px) auto 0;
    }
    .st-key-alba_chat_empty [data-testid="stChatInput"],
    [data-testid="stBottom"] [data-testid="stChatInput"] {
        max-width: 760px;
        margin-left: auto;
        margin-right: auto;
    }
    [data-testid="stBottom"] {
        background: transparent !important;
    }
    [data-testid="stBottom"] > div {
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    /* The transcript is the primary content, not a list of form controls. */
    [data-testid="stChatMessage"] {
        max-width: 860px;
        margin: 0 auto 1rem;
        border-radius: 16px;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        max-width: min(76%, 730px);
        margin-right: max(0px, calc((100% - 860px) / 2));
        margin-left: auto;
        background: rgba(111, 137, 123, .19);
        border: 1px solid rgba(169,201,180,.12);
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background: transparent;
    }
    @media (max-width: 760px) {
        .st-key-alba_chat_empty {margin-top: 16vh;}
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            max-width: 90%;
            margin-right: 0;
        }
    }

    /* ALBA v2: a focused legal-workspace skin, not an analogue dashboard. */
    [data-testid="stAppViewContainer"] {
        background: #111a18 !important;
        background-image: none !important;
    }
    [data-testid="stHeader"] {background: rgba(17,26,24,.95) !important;}
    [data-testid="stSidebar"] {
        background: #18221e !important;
        border-right: 1px solid rgba(224,237,226,.13) !important;
    }
    [data-testid="stSidebar"]::after {display: none !important;}
    [data-testid="stSidebar"] h2 {
        font-family: inherit !important;
        font-size: 1.45rem !important;
        letter-spacing: -.025em !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: rgba(169,201,180,.10) !important;
        border: 1px solid rgba(169,201,180,.14) !important;
        box-shadow: none !important;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1280px;
        padding-top: 1.05rem;
        padding-bottom: 8.5rem;
    }
    .alba-workspace-kicker {
        color: #a9c9b4;
        text-transform: uppercase;
        font-size: .73rem;
        letter-spacing: .12em;
        font-weight: 650;
        margin-bottom: .18rem;
    }
    [data-testid="stChatMessage"] {
        max-width: 900px;
        border-radius: 13px;
    }
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background: #24352e !important;
        border: 1px solid rgba(169,201,180,.11) !important;
    }
    .st-key-alba_sources_panel {
        border-left: 1px solid rgba(169,201,180,.20);
        padding-left: 1.1rem;
        min-height: 240px;
    }
    .st-key-alba_chat_empty {margin-top: clamp(20px, 7vh, 75px);}
    .stButton > button[kind="primary"] {
        background: #aacbb7 !important;
        color: #1a2b22 !important;
        border-color: #aacbb7 !important;
        box-shadow: none !important;
    }
    @media (max-width: 760px) {
        [data-testid="stMainBlockContainer"] {padding-top: .55rem;}
        .st-key-alba_sources_panel {border-left: 0; padding-left: 0; min-height: 0;}
        .st-key-alba_chat_empty {margin-top: 1.2rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
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
    if st.button("＋ New chat", key="alba_new_chat", icon=":material/add_comment:", use_container_width=True):
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
    with st.popover("History backup", icon=":material/history:"):
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
st.markdown(
    '<div class="alba-workspace-kicker">ALBA / Legal workspace</div>',
    unsafe_allow_html=True,
)
header_left, header_right = st.columns([5, 1], vertical_alignment="center")
with header_left:
    st.markdown("**Legal Assistant**")
with header_right:
    if st.button(
        "Sources", key="alba_sources_toggle", icon=":material/bookmarks:",
        use_container_width=True,
        help="Open the official references and document excerpts for this chat",
    ):
        st.session_state["alba_sources_open"] = not st.session_state.get(
            "alba_sources_open", False
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
        mode = "general"
        messages = []
    if not conversation:
        st.markdown(
            '<div class="alba-welcome-eyebrow">LEGAL RESEARCH & DRAFTING</div>'
            '<div class="alba-welcome-title">How can I help with your legal work?</div>'
            '<div class="alba-welcome-subtitle">'
            'Ask about Albanian or EU law, analyse a public document, '
            'or open a dedicated drafting tool.'
            '</div>',
            unsafe_allow_html=True,
        )
        st.caption("ALBA answers in your language. Official legal status is confirmed only when the source has been checked.")
        quick_a, quick_b, quick_c = st.columns(3, gap="small")
        with quick_a:
            if st.button(
                "Legal drafting", key="alba_shortcut_legal_drafting",
                icon=":material/gavel:", use_container_width=True,
            ):
                st.switch_page("pages/3_Legal_Drafting.py")
        with quick_b:
            if st.button(
                "Table of Concordance", key="alba_shortcut_toc",
                icon=":material/table_chart:", use_container_width=True,
            ):
                st.switch_page("pages/1_ToC_Builder.py")
        with quick_c:
            if st.button(
                "EU reporting", key="alba_shortcut_reporting",
                icon=":material/article:", use_container_width=True,
            ):
                st.switch_page("pages/4_EU_Reporting.py")

if show_sources:
    with sources_area:
        with st.container(key="alba_sources_panel"):
            st.markdown("**Sources & documents**")
            source_tab, document_tab = st.tabs(["Official sources", "Documents"])
            with source_tab:
                st.caption(
                    "Official links you shared. Their content, status and "
                    "consolidated versions have not yet been independently verified "
                    "by this chat."
                )
                cited_links = user_source_links(messages)
                if cited_links:
                    for source in cited_links:
                        st.link_button(
                            source["label"], source["url"],
                            use_container_width=True,
                        )
                else:
                    st.caption("No official document links in this conversation.")
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
                        "Documents uploaded using + appear here after "
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

# A blank chat gets a centered input. Once it has messages, the very same
# native chat widget is placed at root level and Streamlit docks it below.
chat_input_options = dict(
    key="alba_chat_prompt",
    max_chars=MAX_USER_CHARS,
    max_upload_size=12,
    accept_file=True,
    file_type=["docx", "xlsx", "pdf", "pptx"],
    disabled=not (account and api_key) or bool(pending_attachment),
)
if conversation:
    submission = st.chat_input(
        "Message…", **chat_input_options,
    )
else:
    with st.container(key="alba_chat_empty"):
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
    uploads = (
        [] if isinstance(submission, str)
        else list(submission.files)
    )
    if uploads:
        # The native + permits one file and only Office/PDF formats. The
        # server-side privacy gate validates actual bytes and content.
        document = uploads[0]
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

