"""Dedicated EU Communication & Reporting page inside the ALBA navigation.

Only public/synthetic information is accepted in this prototype. A separate
user-triggered Generate action is required for any external model processing.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from communication_studio import (
    EU_REPORTING_FORMATS,
    FORMATS,
    build_messages,
    extract_publishable_text,
    generate_communication,
    load_library,
    qa_flags,
)
from privacy_guard import BLOCK_NOTICE, combine_safe_text, scan_text_fields
from public_upload_ui import selected_public_attachment
from ui_copy import friendly_error
from review_ui import render_auto_review
from ui_theme import apply_theme

st.set_page_config(page_title="ALBA | EU Communication & Reporting",
                   page_icon="🇪🇺", layout="wide")
apply_theme("EU")
st.title("EU Communication & Reporting")
st.caption("Public sources only · Verify drafts before submission.")

@st.cache_data(show_spinner=False)
def reporting_library():
    return load_library()

try:
    _, communication_rules, albanian_rules = reporting_library()
except (OSError, ValueError, KeyError):
    st.error("The editorial library could not be loaded.")
    st.stop()

report_formats = [
    "information_note",
    "administrative_capacity",
    "progress_report",
    "negotiating_position",
    "eu_letter",
]
assert set(report_formats) == EU_REPORTING_FORMATS

a, b = st.columns(2)
with a:
    report_format = st.selectbox(
        "1. Reporting document",
        options=report_formats,
        format_func=lambda value: FORMATS[value]["label"],
        key="eu_document_type",
    )
    organisation = st.text_input(
        "Reporting institution (optional)", max_chars=140,
        key="eu_institution",
    )
with b:
    output_language = st.selectbox(
        "2. Output language", ["en", "sq"],
        format_func=lambda code: "English" if code == "en" else "Albanian",
        key="eu_output_language",
    )
    audience = st.text_input(
        "Recipient / audience (optional)", max_chars=160,
        key="eu_audience",
    )

mode = st.radio(
    "3. Drafting task",
    options=["create", "review", "adapt"],
    format_func=lambda value: {
        "create": "Prepare a new document",
        "review": "Review an existing draft",
        "adapt": "Adapt text to the selected EU reporting format",
    }[value],
    horizontal=True,
    key="eu_mode",
)
objective = st.text_input(
    "Objective / reporting scope (optional)", max_chars=240, key="eu_objective"
)
st.text_area(
    "4. Verified source facts, legislation and operational evidence",
    key="eu_source", height=265, max_chars=8000,
    placeholder=(
        "Provide sourced national measures, adoption / draft status, mandate, "
        "FTE, inspections, periods, outcomes, gaps and confirmed commitments. "
        "For review or adapt, paste the existing text."
    ),
)
attachment = st.file_uploader(
    "Optional public supporting file (TXT, MD, DOCX or text-based PDF)",
    type=["txt", "md", "docx", "pdf"], key="eu_attachment",
    help="Public PDF/DOCX files with logos are accepted if readable; select a section from long files.",
)
confirm = st.checkbox(
    "I confirm all material is public or synthetic and contains no personal "
    "or confidential information.",
    key="eu_public_confirm",
)
if scan_text_fields(
    st.session_state.get("eu_source", ""), organisation, audience, objective,
    public_legal=True,
).blocked:
    st.session_state.pop("eu_report_draft", None)
    st.session_state.pop("eu_report_key", None)
    st.error(BLOCK_NOTICE)
    st.stop()

uploaded_text, upload_digest = selected_public_attachment(
    attachment,
    current_text=st.session_state.get("eu_source", ""),
    context_limit=8000,
    state_prefix="eu_public",
)
try:
    source = combine_safe_text(
        st.session_state.get("eu_source", ""), uploaded_text,
        max_chars=8000, public_legal=True,
    )
except ValueError as exc:
    st.error(friendly_error(exc, context="communication"))
    st.stop()

fingerprint = hashlib.sha256(
    json.dumps({
        "source": source, "upload_digest": upload_digest, "format": report_format, "language": output_language,
        "mode": mode, "institution": organisation, "recipient": audience,
        "scope": objective,
    }, sort_keys=True, ensure_ascii=False).encode("utf-8")
).hexdigest()

if st.button("Generate EU reporting draft", type="primary", key="eu_generate"):
    if not confirm:
        st.warning("Confirm the public/synthetic-material declaration.")
    elif not source.strip():
        st.warning("Provide public evidence or a draft to review.")
    else:
        try:
            account = st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
            token = st.secrets.get("CLOUDFLARE_API_TOKEN", "").strip()
        except Exception:
            account, token = "", ""
        if not account or not token:
            st.error("Cloudflare credentials are not configured.")
        else:
            try:
                messages = build_messages(
                    format_id=report_format, mode=mode, source_text=source,
                    organization=organisation, audience=audience,
                    objective=objective, visual_description="",
                    output_language=output_language,
                    communication_rules=communication_rules,
                    albanian_rules=albanian_rules,
                    public_legal_source=True,
                )
                with st.spinner("Preparing the reporting document..."):
                    draft = generate_communication(messages, account, token, public_legal_source=True)
                if scan_text_fields(draft, public_legal=True).blocked:
                    raise ValueError(BLOCK_NOTICE)
                st.session_state["eu_report_draft"] = draft
                st.session_state["eu_report_key"] = fingerprint
            except ValueError as exc:
                st.error(friendly_error(exc, context="communication"))

if (
    confirm and st.session_state.get("eu_report_key") == fingerprint
    and st.session_state.get("eu_report_draft")
):
    st.divider()
    st.subheader("Reporting draft – for institutional review")
    st.text_area(
        "Editable draft and pre-submission verification notes",
        key="eu_report_draft", height=440,
    )
    revised = st.session_state["eu_report_draft"]
    if scan_text_fields(revised, public_legal=True).blocked:
        st.session_state.pop("eu_report_draft", None)
        st.session_state.pop("eu_report_key", None)
        st.error(BLOCK_NOTICE)
        st.stop()
    with st.expander("Evidence and editorial checks", expanded=False):
        checks = qa_flags(source, revised, report_format)
        if checks:
            for item in checks:
                st.write("• " + item)
        else:
            st.write("No heuristic alerts were detected; this does not verify the evidence.")

    transmission = extract_publishable_text(revised)
    if transmission:
        st.download_button(
            "Download text for institutional review (.txt)",
            data=transmission.encode("utf-8"),
            file_name="ALBA_EU_Reporting_DRAFT.txt",
            mime="text/plain; charset=utf-8",
        )

    render_auto_review(
        kind="eu_reporting",
        source_text=(
            "Reporting institution (not independently verified): " + organisation +
            "\nRecipient: " + audience +
            "\nReporting scope: " + objective +
            "\nVerified source evidence:\n" + source
        ),
        draft_text=revised,
        task=report_format,
        context_id="eu_reporting",
        public_confirmed=confirm,
    )
