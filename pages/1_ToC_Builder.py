"""ALBA ToC Builder: one directive upload, one Word Table of Concordance.

The standard seven-column format is built in. An Albanian source can be
downloaded directly; an English source is translated literally to Albanian
after one explicit Generate click. All provisions are handled automatically
within resource limits. Translation progress resumes in the same session.
"""
from __future__ import annotations

import hashlib
import streamlit as st

from toc_workflow import prepare_toc, export_word
from toc_translation import translate_unit
from privacy_guard import BLOCK_NOTICE, scan_text_fields
from ui_copy import friendly_error
from ui_theme import apply_theme

st.set_page_config(page_title="ALBA | ToC Builder", page_icon="📄", layout="wide")
apply_theme("TOC")
st.title("ToC Builder")
st.caption("Ngarko direktivën në PDF ose Word. ALBA krijon Tabelën e Përputhshmërisë në Word.")

source = st.file_uploader(
    "Ngarko direktivën",
    type=["pdf", "docx"],
    key="toc_source_file",
    help="Dokumenti duhet të jetë publik dhe të përmbajë tekst të lexueshëm.",
)
if source is None:
    st.stop()

# The same full directive is reused across automatic translation reruns.
# Cache only within this user's session, not in a server-wide data cache.
file_bytes = source.getvalue()
file_id = hashlib.sha256(source.name.encode("utf-8") + b"\0" + file_bytes).hexdigest()[:24]
if st.session_state.get("toc_prepared_source") != file_id:
    try:
        prepared_source = prepare_toc(source.name, file_bytes)
    except (ValueError, AssertionError) as exc:
        st.error(friendly_error(exc, context="toc"))
        st.stop()
    st.session_state["toc_prepared_source"] = file_id
    st.session_state["toc_prepared_data"] = prepared_source
prepared = st.session_state["toc_prepared_data"]

st.write(
    f"**{prepared.title}** · "
    f"{'Shqip' if prepared.language == 'sq' else 'Anglisht → Shqip'} · "
    f"{len(prepared.units)} njësi"
)
if prepared.warnings:
    with st.expander("Shënime për dokumentin"):
        for note in prepared.warnings:
            st.write(note)

if prepared.language == "sq":
    # No AI service is needed when the source is already in Albanian.
    try:
        document = export_word(prepared)
    except (ValueError, AssertionError) as exc:
        st.error(friendly_error(exc, context="toc"))
        st.stop()
    st.download_button(
        "Shkarko ToC në Word (.docx)",
        data=document,
        file_name="ALBA_ToC_Tabela_e_Perputhshmerise.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary",
        use_container_width=True,
    )
    st.stop()

# English directives need an explicit user click to transmit public source
# provisions to Cloudflare Workers AI. Do not add extra configuration fields.
def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""

account_id = _secret("CLOUDFLARE_ACCOUNT_ID")
api_token = _secret("CLOUDFLARE_API_TOKEN")
if not account_id or not api_token:
    st.error("Përkthimi AI nuk është i konfiguruar në ALBA.")
    st.stop()

if st.session_state.get("toc_single_source_id") != prepared.source_id:
    st.session_state["toc_single_source_id"] = prepared.source_id
    st.session_state["toc_single_translations"] = {}
    st.session_state["toc_single_running"] = False
    st.session_state["toc_single_error"] = None
    st.session_state["toc_single_checks"] = {}

translations = st.session_state["toc_single_translations"]
pending = [unit for unit in prepared.units if not translations.get(unit.reference, "").strip()]
done = len(prepared.units) - len(pending)

if pending:
    st.progress(done / len(prepared.units), text=f"Përkthyer {done} nga {len(prepared.units)} njësi")
    if not st.session_state["toc_single_running"]:
        if st.session_state.get("toc_single_error"):
            st.error(st.session_state["toc_single_error"])
        label = "Krijo ToC në Word" if not done else "Vazhdo konvertimin"
        if st.button(label, type="primary", use_container_width=True):
            st.session_state["toc_single_error"] = None
            st.session_state["toc_single_running"] = True
            st.rerun()

    if st.session_state["toc_single_running"]:
        # One click starts the whole conversion. Short batches permit UI
        # updates and retaining successfully translated units across reruns.
        with st.spinner("Po përkthehet direktiva në shqip…"):
            for unit in pending[:3]:
                try:
                    result, checks = translate_unit(
                        unit, account_id=account_id, api_token=api_token,
                    )
                    if scan_text_fields(result, public_legal=True).blocked:
                        raise ValueError(BLOCK_NOTICE)
                    translations[unit.reference] = result
                    st.session_state["toc_single_checks"][unit.reference] = checks
                except (ValueError, AssertionError) as exc:
                    st.session_state["toc_single_error"] = (
                        "U arrit kufiri i përkthimit në Cloudflare. "
                        "Puna e përfunduar mbetet në këtë sesion."
                        if "429" in str(exc) else friendly_error(exc, context="toc")
                    )
                    st.session_state["toc_single_running"] = False
                    break
        st.session_state["toc_single_translations"] = translations
        if st.session_state["toc_single_running"]:
            # Continue automatically until every source provision is done;
            # do not require the user to operate a batch selector.
            st.rerun()
        else:
            st.rerun()
    st.stop()

try:
    result = export_word(prepared, translations)
except (ValueError, AssertionError) as exc:
    st.error(friendly_error(exc, context="toc"))
    st.stop()

checks = st.session_state.get("toc_single_checks", {})
flagged = {key: value for key, value in checks.items() if value}
if flagged:
    st.warning(
        "Disa referenca ose numra duhen verifikuar kundrejt direktivës origjinale."
    )
    with st.expander("Kontrollet e përkthimit"):
        for key, issues in flagged.items():
            for issue in issues:
                st.write(f"{key}: {issue}")

st.download_button(
    "Shkarko ToC në Word (.docx)",
    data=result,
    file_name="ALBA_ToC_Tabela_e_Perputhshmerise.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    type="primary",
    use_container_width=True,
)
