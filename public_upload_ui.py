"""Shared public-document upload workflow for ALBA Streamlit modules.

Read and screen the *whole* uploaded document before presenting an excerpt.
Never silently truncate a file or send the full document to an AI model.
Public document context permits legal/privacy vocabulary while actual names,
emails, identifiers, credentials and classified document markings are blocked.
"""
from __future__ import annotations

import hashlib

import streamlit as st

from privacy_guard import screen_upload, upload_block_message


def selected_public_attachment(
    upload,
    *,
    current_text: str,
    context_limit: int,
    state_prefix: str,
    extra_context_length: int = 0,
) -> tuple[str, str]:
    """Return (selected screened text, file fingerprint), or stop on unsafe input.

    A longer legal/public document remains readable in a disabled preview; the
    user can edit/select the specific provisions to send to the model.
    """
    if upload is None:
        return "", ""

    data = upload.getvalue()
    fingerprint = hashlib.sha256(data).hexdigest()
    result = screen_upload(
        upload.name, data, max_chars=250000, public_legal=True
    )
    if result.blocked:
        st.error(upload_block_message(result.reason))
        st.stop()
    if result.warning:
        st.warning(result.warning)

    available = context_limit - len(current_text) - extra_context_length - 8
    if available < 200:
        st.error(
            "The typed text already fills the AI request. Shorten the text "
            "to include an attachment section."
        )
        st.stop()

    if len(result.text) <= available:
        return result.text, fingerprint

    st.caption("Long document: choose the section to analyse.")
    selection_key = state_prefix + "_selected_excerpt"
    identity_key = state_prefix + "_excerpt_signature"
    identity = f"{fingerprint}:{available}"
    if st.session_state.get(identity_key) != identity:
        st.session_state[selection_key] = result.text[:available]
        st.session_state[identity_key] = identity

    with st.expander("Read the full extracted text", expanded=False):
        st.text_area(
            "Extracted source – copy only the relevant section",
            value=result.text,
            height=300,
            disabled=True,
            key=state_prefix + "_read_only_" + fingerprint[:12],
        )

    excerpt = st.text_area(
        "Excerpt / article(s) to include",
        height=230,
        max_chars=available,
        key=selection_key,
    )
    return excerpt, fingerprint
