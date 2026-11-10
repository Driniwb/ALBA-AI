"""ALBA AI 3.2 — Word ToC Builder with literal EN->SQ translation.

Streamlit auto-discovers this page from the pages/ directory. It does not
overwrite the main language editor. Uploaded content is held in the current
session and is not committed to GitHub. Translation invokes Cloudflare ONLY
after the user explicitly clicks the translation button.
"""
import hashlib

import streamlit as st

from toc_builder import (
    Provision,
    extract_document,
    normalise_pdf_display,
    pdf_extraction_flags,
)
from toc_template import built_in_blank_toc, create_toc_using_template
from toc_translation import translate_unit, translated_provisions
from toc_units import first_n_articles
from privacy_guard import BLOCK_NOTICE, scan_text_fields, screen_upload
from ui_theme import apply_theme
from ui_copy import friendly_error

st.set_page_config(
    page_title="ALBA | ToC Builder",
    page_icon="📄",
    layout="wide",
)
apply_theme("TOC")
st.title("ToC Builder")
st.caption("Legal concordance · Literal English-to-Albanian translation · Word")

st.warning(
    "Experimental legal drafting tool, not an automatic transposition assessment. "
    "Use public or synthetic documents only. Do not upload personal, internal or confidential material."
)
st.write(
    "Upload a text-based EU directive in PDF or Word. ALBA extracts individual "
    "provisions and prepares a seven-column concordance table in Word. "
    "The Albanian translation is a draft for expert review; national-law mappings "
    "and compliance assessments stay blank."
)

source = st.file_uploader(
    "1. Directive in English (text-based PDF or DOCX)",
    type=["pdf", "docx"],
    key="toc_source_file",
)
template = st.file_uploader(
    "2. Blank Word ToC template (DOCX) – optional",
    type=["docx"],
    key="toc_blank_template_file",
    help=(
        "Upload your blank Word template to retain its layout. "
        "Otherwise ALBA creates a sample seven-column template."
    ),
)
@st.cache_data(show_spinner=False)
def cached_alba_blank_template():
    # Keep byte-for-byte stable across Streamlit reruns and translation steps.
    return built_in_blank_toc()

template_bytes = template.getvalue() if template else cached_alba_blank_template()
st.download_button(
    "Download blank ToC template (7 columns)",
    data=cached_alba_blank_template(),
    file_name="ALBA_ToC_model_bosh_7_kolona.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)

c1, c2 = st.columns([2, 1])
with c1:
    title = st.text_input(
        "Directive title in the ToC",
        value="",
        placeholder="Enter the directive number and title",
        max_chars=200,
    )
with c2:
    article_count = st.selectbox(
        "Articles to include in this pilot",
        [1, 2, 3],
        index=0,
        help="This pilot handles Articles 1–3 only.",
    )
mode = st.radio(
    "Content of column 2",
    ["Literal Albanian translation (AI)", "Original text (no translation)"],
    horizontal=True,
)
cleanup = st.checkbox(
    "Clean PDF page markers and line-break artifacts",
    value=True,
    help=(
        "Mechanical cleanup does not certify the accuracy of the text. "
        "Always verify the original publication."
    ),
)
confirmed = st.checkbox(
    "I confirm these files are public or synthetic and contain no confidential information."
)

if source is None:
    st.info("Upload a directive to begin.")
    st.stop()
if not confirmed:
    st.info("Confirm the safe-use statement to proceed.")
    st.stop()

# Local preflight covers the *entire* document and blank Word template.
# Uploaded bytes are not sent to Cloudflare. Block files with uninspectable
# pages, embedded images, sensitive markers or personal identifiers.
toc_file_check = screen_upload(
    source.name, source.getvalue(), max_chars=150000
)
template_file_check = (
    screen_upload(template.name, template.getvalue(), max_chars=50000)
    if template is not None else None
)
if (
    toc_file_check.blocked
    or (template_file_check is not None and template_file_check.blocked)
    or scan_text_fields(title).blocked
):
    st.session_state.pop("toc_translations", None)
    st.session_state.pop("toc_checks", None)
    st.error(BLOCK_NOTICE)
    st.stop()

try:
    extracted = extract_document(source.name, source.getvalue())
    units = first_n_articles(extracted.text, article_count)
    found = pdf_extraction_flags("\n".join(unit.text for unit in units))
    if extracted.warnings:
        st.warning(
            "Automatic text extraction may change line order, footnotes or numbering. "
            "Check each provision against the official document."
        )
    if found:
        st.warning(
            "Possible PDF page markers or split words were detected. "
            "Review the extracted text before using it."
        )
    if source.name.lower().endswith(".pdf") and cleanup:
        units = [
            Provision(unit.reference, normalise_pdf_display(unit.text))
            for unit in units
        ]
    if not units or any(not unit.text.strip() for unit in units):
        raise ValueError("No usable provisions could be extracted.")
    if len(set(u.reference for u in units)) != len(units):
        raise ValueError("Duplicate provision references were found.")
    # Validate format without touching any file on disk.
    from toc_template import validate_blank_template
    validate_blank_template(template_bytes)
except (ValueError, AssertionError) as error:
    st.error(friendly_error(error, context="toc"))
    st.stop()

st.subheader("Extracted provisions")
st.metric("ToC rows", len(units))
st.dataframe(
    [
        {
            "Article / subdivision": u.reference,
            "Characters": len(u.text),
            "Source text preview": u.text[:120],
        }
        for u in units
    ],
    hide_index=True,
    use_container_width=True,
)
with st.expander("Preview first extracted provision"):
    st.text(units[0].text[:3800])

if mode == "Original text (no translation)":
    try:
        docx = create_toc_using_template(template_bytes, units, title.strip())
        st.download_button(
            "Download ToC in Word (original text)",
            data=docx,
            file_name="ALBA_ToC_tekst_origjinal_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except (ValueError, AssertionError) as error:
        st.error(friendly_error(error, context="toc"))
    st.stop()

try:
    api_token = st.secrets.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
except Exception:
    api_token = ""
    account_id = ""

if not api_token or not account_id:
    st.error(
        "Cloudflare Workers AI is not configured for translation. "
        "You can still export the ToC with original-language text."
    )
    st.stop()

fingerprint = hashlib.sha256(
    source.getvalue()
    + template_bytes
    + str(article_count).encode()
    + str(cleanup).encode()
).hexdigest()[:20]
if st.session_state.get("toc_active_fingerprint") != fingerprint:
    st.session_state["toc_active_fingerprint"] = fingerprint
    st.session_state["toc_translations"] = {}
    st.session_state["toc_checks"] = {}

translated = st.session_state["toc_translations"]
checks = st.session_state["toc_checks"]
pending = [u for u in units if not translated.get(u.reference, "").strip()]

st.subheader("Literal English-to-Albanian translation")
st.caption(
    "Translation runs provision by provision for easier review of numbering, "
    "terminology and completeness. AI translation is not authoritative."
)
st.progress((len(units) - len(pending)) / len(units))
st.write(f"Translated: **{len(units) - len(pending)} / {len(units)}**")
batch = st.selectbox(
    "Provisions to translate per click",
    [1, 2, 3, 4],
    index=2,
)

if st.button(
    "Translate next provisions into Albanian",
    type="primary",
    disabled=not pending,
):
    work = pending[:batch]
    progress = st.progress(0.0)
    for i, unit in enumerate(work, start=1):
        try:
            with st.spinner("Translating: " + unit.reference):
                result, warnings = translate_unit(unit, account_id, api_token)
            if scan_text_fields(result).blocked:
                raise ValueError(BLOCK_NOTICE_SQ)
            translated[unit.reference] = result
            checks[unit.reference] = warnings
        except ValueError as error:
            st.error(f"{unit.reference}: {error}")
            break
        progress.progress(i / len(work))
    st.session_state["toc_translations"] = translated
    st.session_state["toc_checks"] = checks
    st.rerun()

# Do not display previously generated content if it fails a fresh check.
if any(scan_text_fields(value).blocked for value in translated.values()):
    st.session_state["toc_translations"] = {}
    st.error(BLOCK_NOTICE)
    st.stop()

reviewed = [u for u in units if translated.get(u.reference)]
if reviewed:
    current = st.selectbox(
        "Review or edit a translated provision",
        options=[u.reference for u in reviewed],
        key="toc_review_reference",
    )
    original = next(u.text for u in units if u.reference == current)
    st.text_area("Original (read-only)", original, height=160, disabled=True)
    edit_key = "toc_review_edit_" + fingerprint + "_" + current
    if edit_key not in st.session_state:
        st.session_state[edit_key] = translated[current]
    edited = st.text_area("Albanian translation (editable)", key=edit_key, height=180)
    if st.button("Save translation edit"):
        if scan_text_fields(edited).blocked:
            st.error(BLOCK_NOTICE)
        elif not edited.strip():
            st.error("Translation cannot be empty.")
        else:
            from toc_translation import translation_warnings
            translated[current] = edited
            checks[current] = translation_warnings(original, edited)
            st.session_state["toc_translations"] = translated
            st.session_state["toc_checks"] = checks
            st.success("Your change has been saved for this session.")
    flagged = {
        k: v for k, v in checks.items()
        if v and k in [u.reference for u in units]
    }
    if flagged:
        with st.expander("Number and terminology checks"):
            for ref, alerts in flagged.items():
                for alert in alerts:
                    st.warning(ref + ": " + alert)

if all(translated.get(u.reference, "").strip() for u in units):
    try:
        translated_units = translated_provisions(units, translated)
        docx = create_toc_using_template(
            template_bytes, translated_units, title.strip()
        )
        st.download_button(
            "Download Albanian ToC – Word (.docx)",
            data=docx,
            file_name="ALBA_ToC_PERKTHIM_LITERAL_SQ_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        st.warning(
            "Compare every provision with the official source. Automated splitting "
            "and translation require expert verification; especially check lettered lists."
        )
    except (ValueError, AssertionError) as error:
        st.error(friendly_error(error, context="toc"))
else:
    st.info(
        "Translate all selected provisions before exporting the Albanian Word ToC."
    )
