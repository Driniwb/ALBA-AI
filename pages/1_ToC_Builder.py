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
from privacy_guard import BLOCK_NOTICE_SQ, scan_text_fields, screen_upload

st.set_page_config(
    page_title="ALBA AI – ToC Builder",
    page_icon="📄",
    layout="wide",
)
st.title("ALBA AI – ToC Builder")
st.caption("Version 3.2 · Provë publike · Direktiva EN → shqip juridike literale · Word")

st.warning(
    "Ky funksion është prototip për redaktim juridik, JO transpozim automatik. "
    "Përdorni vetëm dokumente publike ose sintetike, pa të dhëna personale, "
    "materiale të brendshme apo dokumente konfidenciale."
)
st.write(
    "Ngarkoni direktivën në PDF me tekst ose Word. ALBA nxjerr njësitë "
    "normative, i përkthen me rendin dhe referencat sa më besnikërisht në "
    "shqip dhe krijon ToC në Word me 7 kolona. Legjislacioni shqiptar, "
    "vlerësimi i përputhshmërisë dhe komentet mbeten bosh."
)

source = st.file_uploader(
    "1. Direktiva në anglisht (.pdf me tekst ose .docx)",
    type=["pdf", "docx"],
    key="toc_source_file",
)
template = st.file_uploader(
    "2. Modeli bosh ToC në Word (.docx) – opsional",
    type=["docx"],
    key="toc_blank_template_file",
    help=(
        "Për të njëjtin formatim si modeli juaj, ngarkoni Word-in bosh. "
        "Pa këtë skedar, ALBA përdor një model sintetik me të njëjtat 7 kolona."
    ),
)
@st.cache_data(show_spinner=False)
def cached_alba_blank_template():
    # Keep byte-for-byte stable across Streamlit reruns and translation steps.
    return built_in_blank_toc()

template_bytes = template.getvalue() if template else cached_alba_blank_template()
st.download_button(
    "Shkarko modelin bosh ALBA (7 kolona)",
    data=cached_alba_blank_template(),
    file_name="ALBA_ToC_model_bosh_7_kolona.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)

c1, c2 = st.columns([2, 1])
with c1:
    title = st.text_input(
        "Titulli i direktivës në ToC",
        value="Direktiva 2008/68/KE",
        max_chars=200,
    )
with c2:
    article_count = st.selectbox(
        "Nenet për këtë provë",
        [1, 2, 3],
        index=0,
        help="Kufizuar në nenet 1–3 për kontrollin fillestar.",
    )
mode = st.radio(
    "Teksti në kolonën 2 të ToC",
    ["Përkthim literal në shqip (AI)", "Teksti origjinal, pa përkthim"],
    horizontal=True,
)
cleanup = st.checkbox(
    "Pastro shënimet e botimit dhe ndarjet teknike të rreshtave në PDF",
    value=True,
    help=(
        "Pastrimi është mekanik, nuk e bën tekstin autentik. "
        "Kontrolloni PDF-në origjinale."
    ),
)
confirmed = st.checkbox(
    "Konfirmoj se të dy dokumentet janë publike ose sintetike dhe "
    "nuk përmbajnë informacion konfidencial."
)

if source is None:
    st.info("Ngarkoni një direktivë për të filluar.")
    st.stop()
if not confirmed:
    st.info("Konfirmoni kushtet e përdorimit për të përpunuar dokumentin.")
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
    st.error(BLOCK_NOTICE_SQ)
    st.stop()

try:
    extracted = extract_document(source.name, source.getvalue())
    units = first_n_articles(extracted.text, article_count)
    found = pdf_extraction_flags("\n".join(unit.text for unit in units))
    for item in extracted.warnings:
        st.warning(item)
    for item in found:
        st.warning(item)
    if source.name.lower().endswith(".pdf") and cleanup:
        units = [
            Provision(unit.reference, normalise_pdf_display(unit.text))
            for unit in units
        ]
    if not units or any(not unit.text.strip() for unit in units):
        raise ValueError("Nuk u nxorën dispozita të përdorshme.")
    if len(set(u.reference for u in units)) != len(units):
        raise ValueError("Referencat e dispozitave rezultojnë të përsëritura.")
    # Validate format without touching any file on disk.
    from toc_template import validate_blank_template
    validate_blank_template(template_bytes)
except (ValueError, AssertionError) as error:
    st.error(str(error))
    st.stop()

st.subheader("Njësitë e nxjerra")
st.metric("Rreshta të ToC-së", len(units))
st.dataframe(
    [
        {
            "Neni / nënndarja": u.reference,
            "Karaktere": len(u.text),
            "Fillimi i tekstit burimor": u.text[:120],
        }
        for u in units
    ],
    hide_index=True,
    use_container_width=True,
)
with st.expander("Kontrollo tekstin e njësisë së parë"):
    st.text(units[0].text[:3800])

if mode == "Teksti origjinal, pa përkthim":
    try:
        docx = create_toc_using_template(template_bytes, units, title.strip())
        st.download_button(
            "Shkarko ToC në Word (tekst origjinal)",
            data=docx,
            file_name="ALBA_ToC_tekst_origjinal_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except (ValueError, AssertionError) as error:
        st.error(str(error))
    st.stop()

try:
    api_token = st.secrets.get("CLOUDFLARE_API_TOKEN", "").strip()
    account_id = st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
except Exception:
    api_token = ""
    account_id = ""

if not api_token or not account_id:
    st.error(
        "Cloudflare Workers AI nuk është konfiguruar për përkthimin. "
        "Modeli ToC pa përkthim mbetet i disponueshëm."
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

st.subheader("Përkthimi literal anglisht–shqip")
st.caption(
    "Përkthimi kryhet njësi për njësi, për të kontrolluar më lehtë "
    "numërtimin, termat dhe mungesat. Është përkthim AI, jo përkthim autentik."
)
st.progress((len(units) - len(pending)) / len(units))
st.write(f"Të përkthyera: **{len(units) - len(pending)} / {len(units)}**")
batch = st.selectbox(
    "Sa njësi të përkthehen me një klikim?",
    [1, 2, 3, 4],
    index=2,
)

if st.button(
    "Përkthe njësitë e radhës në shqip",
    type="primary",
    disabled=not pending,
):
    work = pending[:batch]
    progress = st.progress(0.0)
    for i, unit in enumerate(work, start=1):
        try:
            with st.spinner("Përkthim: " + unit.reference):
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
    st.error(BLOCK_NOTICE_SQ)
    st.stop()

reviewed = [u for u in units if translated.get(u.reference)]
if reviewed:
    current = st.selectbox(
        "Shqyrto ose korrigjo një njësi të përkthyer",
        options=[u.reference for u in reviewed],
        key="toc_review_reference",
    )
    original = next(u.text for u in units if u.reference == current)
    st.text_area("Origjinali (vetëm për krahasim)", original, height=160, disabled=True)
    edit_key = "toc_review_edit_" + fingerprint + "_" + current
    if edit_key not in st.session_state:
        st.session_state[edit_key] = translated[current]
    edited = st.text_area("Përkthimi në shqip (mund ta korrigjoni)", key=edit_key, height=180)
    if st.button("Ruaj korrigjimin për këtë njësi"):
        if scan_text_fields(edited).blocked:
            st.error(BLOCK_NOTICE_SQ)
        elif not edited.strip():
            st.error("Përkthimi nuk mund të jetë bosh.")
        else:
            from toc_translation import translation_warnings
            translated[current] = edited
            checks[current] = translation_warnings(original, edited)
            st.session_state["toc_translations"] = translated
            st.session_state["toc_checks"] = checks
            st.success("Korrigjimi u ruajt për këtë sesion.")
    flagged = {
        k: v for k, v in checks.items()
        if v and k in [u.reference for u in units]
    }
    if flagged:
        with st.expander("Kontrolle të numrave dhe terminologjisë"):
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
            "Shkarko ToC në shqip – Word (.docx)",
            data=docx,
            file_name="ALBA_ToC_PERKTHIM_LITERAL_SQ_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
        st.warning(
            "Kontrollo çdo nen dhe nënndarje kundrejt PDF-së origjinale. "
            "Përkthimi AI dhe ndarja automatike nuk janë verifikuar juridikisht; "
            "sidomos pas listave me shkronja mund të nevojitet ndarje manuale."
        )
    except (ValueError, AssertionError) as error:
        st.error(str(error))
else:
    st.info(
        "Për të krijuar dokumentin në shqip, përfundoni përkthimin e "
        "të gjitha njësive të zgjedhura."
    )
