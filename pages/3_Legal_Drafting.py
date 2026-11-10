"""ALBA Legal Drafting page: Albanian laws, VKM, instructions and regulations.

Uses the existing privacy gate. No uploading to a repository, no hidden
analytics, no external request before an explicit Generate click.
"""
from __future__ import annotations
import hashlib
import json
import streamlit as st
from privacy_guard import BLOCK_NOTICE, screen_upload, scan_text_fields, combine_safe_text
from legal_drafting import ACT_TYPES, DRAFT_MODES, build_legal_messages, generate_legal_draft, legal_review_flags
from ui_theme import apply_theme
from ui_copy import friendly_error

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
confirmed = st.checkbox(
    "I confirm that the material is public or synthetic and contains no personal or confidential information.",
    key="legal_confirm",
)
safe_doc = (
    screen_upload(attachment.name, attachment.getvalue(), max_chars=6500)
    if attachment is not None else None
)
if scan_text_fields(st.session_state.get("legal_source", ""),basis,goal,eu_text).blocked or (safe_doc and safe_doc.blocked):
    st.session_state.pop("legal_result",None)
    st.session_state.pop("legal_result_key",None)
    st.error(BLOCK_NOTICE)
    st.stop()
try:
    source = combine_safe_text(
        st.session_state.get("legal_source",""),
        safe_doc.text if safe_doc else "",
        max_chars=10500,
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
            if scan_text_fields(result).blocked:
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
    if scan_text_fields(reviewed).blocked:
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
