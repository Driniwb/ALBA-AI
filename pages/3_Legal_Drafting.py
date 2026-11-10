"""ALBA Legal Drafting page: Albanian laws, VKM, instructions and regulations.

Uses the existing privacy gate. No uploading to a repository, no hidden
analytics, no external request before an explicit Generate click.
"""
from __future__ import annotations
import hashlib
import json
import streamlit as st
from privacy_guard import (
    BLOCK_NOTICE, screen_upload, scan_text_fields, combine_safe_text,
    upload_block_message,
)
from legal_drafting import ACT_TYPES, DRAFT_MODES, build_legal_messages, generate_legal_draft, legal_review_flags
from ui_theme import apply_theme
from ui_copy import friendly_error
from review_ui import render_auto_review

st.set_page_config(page_title="ALBA | Legal Drafting", page_icon="⚖️",layout="wide")
apply_theme("LEGAL")
st.title("Legal Drafting")
st.caption("Albanian normative acts · Drafting technique · EU acquis approximation")
st.warning(
    "Drafting assistance only. No legal act or EU-conformity assessment is certified. "
    "Use only public or synthetic material without personal or confidential data."
)
a, b = st.columns(2)
with a:
    act_type = st.selectbox(
        "1. Type of legal act",
        options=list(ACT_TYPES),
        format_func=lambda value: ACT_TYPES[value]["label"],
        key="legal_act_type",
    )
with b:
    mode = st.selectbox(
        "2. Drafting task", options=list(DRAFT_MODES),
        format_func=lambda value: DRAFT_MODES[value], key="legal_mode"
    )
st.caption("Each act follows its own methodology, delegated competence and structure. Output is in Albanian.")
basis = st.text_input(
    "Legal basis / enabling authority (use exact verified citations)",
    placeholder="Leave empty when unavailable; ALBA will not invent a legal basis.",
    max_chars=1200,
    key="legal_basis",
)
goal = st.text_input("Drafting objective or issue (optional)", max_chars=1200, key="legal_goal")
st.text_area(
    "3. Source material / existing provision",
    key="legal_source",
    placeholder=(
        "Paste the existing article(s), draft or factual drafting instructions. "
        "For amendments, include the exact current wording and its reference."
    ),
    max_chars=10500,
    height=220,
)
eu_text = ""
if mode == "transpose":
    eu_text = st.text_area(
        "4. Exact EU provision to transpose (paste authoritative text)",
        height=175,
        max_chars=10500,
        key="legal_eu_text",
        placeholder="Paste the relevant article, paragraphs and letters from the current EU act.",
    )

attachment = st.file_uploader(
    "Attach a public source document (optional; TXT, MD, DOCX, text-based PDF)",
    type=["txt","md","docx","pdf"], key="legal_file",
    help="Locally screened. Image-based or uninspectable documents are blocked."
)
published_act = st.checkbox(
    "The legal source is an officially published normative act (not an "
    "unpublished draft or an internal institutional document).",
    key="legal_published_act",
    help=(
        "Official laws, decisions, instructions and regulations may contain "
        "the legal terms 'confidential', 'personal data' or 'medical records'. "
        "This category relaxes only these topic-word alerts, never identifiers "
        "or actual confidential classification markings."
    ),
)
confirmed = st.checkbox(
    "I confirm the source is public or synthetic and does not contain "
    "private records or credentials.",
    key="legal_confirm",
)
safe_doc = (
    screen_upload(
        attachment.name, attachment.getvalue(),
        max_chars=200000, public_legal=published_act,
    )
    if attachment is not None else None
)
if safe_doc is not None and safe_doc.blocked:
    st.session_state.pop("legal_result", None)
    st.session_state.pop("legal_result_key", None)
    st.error(upload_block_message(safe_doc.reason))
    st.stop()
if safe_doc and safe_doc.warning:
    st.warning(safe_doc.warning)
if (
    scan_text_fields(
        st.session_state.get("legal_source", ""), eu_text,
        public_legal=published_act,
    ).blocked
    or scan_text_fields(basis, goal, public_legal=published_act).blocked
):
    st.session_state.pop("legal_result", None)
    st.session_state.pop("legal_result_key", None)
    st.error(BLOCK_NOTICE)
    st.stop()

typed_source = st.session_state.get("legal_source", "")
selected_upload = safe_doc.text if safe_doc else ""
if safe_doc:
    remaining = 10500 - len(typed_source) - len(eu_text) - 50
    if len(safe_doc.text) > remaining:
        if remaining < 300:
            st.error(
                "The manually supplied source and EU provision already use "
                "the available context. Shorten those fields to select a section."
            )
            st.stop()
        st.info(
            f"The act was successfully read ({len(safe_doc.text):,} characters). "
            "ALBA cannot reliably analyse an entire long legal act in one "
            "request. Choose the relevant articles below. The field initially "
            "contains the beginning of the act; it is NOT the full document."
        )
        file_signature = hashlib.sha256(
            attachment.getvalue()
        ).hexdigest()
        source_signature = file_signature + ":" + str(remaining)
        if st.session_state.get("legal_last_source_signature") != source_signature:
            st.session_state["legal_selected_excerpt"] = safe_doc.text[:remaining]
            st.session_state["legal_last_source_signature"] = source_signature
        with st.expander("Read extracted document text", expanded=False):
            st.text_area(
                "Extracted source (read-only; copy the article you need)",
                value=safe_doc.text, height=340, disabled=True,
                key="legal_full_extracted_text_" + file_signature[:12],
            )
        selected_upload = st.text_area(
            "Selected article(s) or sections for AI analysis",
            key="legal_selected_excerpt", height=260,
            max_chars=remaining,
        )
try:
    source = combine_safe_text(
        typed_source, selected_upload, max_chars=10500,
        public_legal=published_act,
    )
except ValueError as error:
    st.error(friendly_error(error))
    st.stop()

payload = json.dumps(
    dict(act_type=act_type,mode=mode,source=source,basis=basis,goal=goal,eu=eu_text),
    ensure_ascii=False,sort_keys=True,
)
fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
if st.button("Generate legal draft", type="primary"):
    if not confirmed:
        st.warning("Confirm the public/synthetic-material statement.")
    elif not source.strip():
        st.warning("Provide a source text or attach a readable, public document.")
    else:
        try:
            account = st.secrets.get("CLOUDFLARE_ACCOUNT_ID","").strip()
            token = st.secrets.get("CLOUDFLARE_API_TOKEN","").strip()
            messages = build_legal_messages(
                act_type=act_type, mode=mode, source_text=source,
                enabling_basis=basis, eu_source=eu_text, drafting_goal=goal,
            )
            with st.spinner("Drafting the Albanian legal text..."):
                result = generate_legal_draft(messages,account,token)
            if scan_text_fields(result, public_legal=True).blocked:
                st.error(BLOCK_NOTICE)
                st.stop()
            st.session_state["legal_result"] = result
            st.session_state["legal_result_key"] = fingerprint
        except ValueError as error:
            st.error(friendly_error(error, context="toc"))

if (st.session_state.get("legal_result_key") == fingerprint
    and st.session_state.get("legal_result")):
    st.divider()
    st.subheader("Draft for legal review")
    st.text_area(
        "Editable proposed Albanian legal text and verification notes",
        height=420, key="legal_result",
    )
    reviewed = st.session_state.get("legal_result","")
    if scan_text_fields(reviewed, public_legal=True).blocked:
        st.session_state.pop("legal_result",None)
        st.error(BLOCK_NOTICE)
        st.stop()
    warnings = legal_review_flags(source + "\n" + eu_text,reviewed,mode)
    with st.expander("Legal QA checklist",expanded=False):
        for warning in warnings:
            st.write("• " + warning)
        st.caption("Manual verification of hierarchy, legal basis and EU legal effect is essential.")
    st.download_button(
        "Download draft (.txt)",data=reviewed.encode("utf-8"),
        file_name="ALBA_Legal_Drafting_DRAFT.txt",
        mime="text/plain; charset=utf-8",
    )

    render_auto_review(
        kind="legal",
        source_text=(
            "Provided enabling basis (not verified): " + basis +
            "\nDrafting objective: " + goal +
            "\nOriginal material:\n" + source
        ),
        draft_text=reviewed,
        eu_text=eu_text,
        task=mode,
        context_id="legal",
        public_confirmed=confirmed,
    )
