"""RIA Builder – staged drafting in the Albanian Annex 2 report format."""
from __future__ import annotations

import hashlib
import json
import streamlit as st

from privacy_guard import screen_upload, upload_block_message, scan_text_fields, BLOCK_NOTICE
from ria_builder import (
    RIA_SECTIONS, RIA_EXEMPTIONS, REFERENCE_NOTES,
    build_ria_messages, generate_ria_section, report_docx,
)
from ui_theme import apply_theme
from ui_copy import friendly_error

st.set_page_config(page_title="ALBA | RIA Builder", page_icon="📋", layout="wide")
apply_theme("LEGAL")
st.title("Regulatory Impact Assessment (RIA)")
st.caption(
    "Vlerësim i ndikimit (VN) · Modeli shqiptar, VKM 584/2003, Shtojca 2. "
    "Përgatitje sipas seksioneve – kontroll juridik dhe metodologjik i domosdoshëm."
)

with st.expander("Metodologjia dhe burimet referuese"):
    for ref in REFERENCE_NOTES:
        st.markdown("- " + ref)
    st.info(
        "Rregullat shqiptare dhe Shtojca 2 përcaktojnë formatin; "
        "Better Regulation i BE-së përdoret vetëm si ndihmë analitike. "
        "Kopja e VKM-së e ofruar pasqyron ndryshimet deri në tetor 2025. "
        "Verifikoni QBZ për përditësimet e mëvonshme."
    )
    st.link_button("VKM 584/2003 – QBZ (akt)", "https://qbz.gov.al/eli/vendim/2003/08/28/584")

st.markdown("**1. Identifikimi i nismës**")
one, two, three = st.columns(3, gap="medium")
with one:
    title = st.text_input(
        "Emërtimi i propozimit", key="ria_title",
        placeholder="Projektligj / projekt-VKM për…", max_chars=350,
    )
    ministry = st.text_input(
        "Ministria udhëheqëse", key="ria_ministry", max_chars=180,
    )
with two:
    phase = st.selectbox(
        "Faza e VN-së", ["Zhvillim", "Konsultim", "Finale"],
        key="ria_phase",
    )
    origin = st.selectbox(
        "Burimi i nismës", ["I brendshëm", "Transpozim i BE-së", "Ndërkombëtar"],
        key="ria_origin",
    )
with three:
    eu_act = st.text_input(
        "Akt i BE-së, nëse ka", key="ria_eu_act",
        placeholder="CELEX dhe titulli i verifikuar", max_chars=300,
    )
    exemption = st.selectbox(
        "Kontroll paraprak i përjashtimit nga VN",
        RIA_EXEMPTIONS, key="ria_exemption",
    )
    if exemption != RIA_EXEMPTIONS[0]:
        st.warning(
            "Kjo kategori është sinjal për analizë sipas pikës 45/1, "
            "jo përjashtim automatik. Arsyetimi dhe konfirmimi janë "
            "përgjegjësi e institucionit."
        )

if origin == "Transpozim i BE-së":
    st.caption(
        "Për përafrimin me acquis, status quo përdoret për krahasim, "
        "jo automatikisht si opsion për të mos përmbushur angazhimin. "
        "Krahasoni mënyrën dhe fazat e zbatimit që lejon acquis."
    )

st.markdown("**2. Të dhënat dhe provat e nismës**")
context = st.text_area(
    "Përshkrimi i problemit, baza faktike, kuadri ligjor dhe objektivat",
    key="ria_evidence", height=190, max_chars=10000,
    placeholder=(
        "Jepni vetëm fakte publike, dispozita ose të dhëna të identifikuara "
        "qartë. Shënoni burimin dhe datën për çdo statistikë."
    ),
)
options = st.text_area(
    "Opsionet për krahasim (përfshirë Opsionin 0 – status quo)",
    key="ria_options", height=110, max_chars=3500,
    placeholder=(
        "Skenari aktual / status quo: …\n"
        "Opsioni 1 – mënyra e zbatimit: …\n"
        "Opsioni 2 – alternativë e lejueshme: …"
    ),
)
consultation = st.text_area(
    "Konsultimet dhe vlerësimet e kostove/përfitimeve të dokumentuara (opsionale)",
    key="ria_consultation", height=100, max_chars=2000,
    placeholder="Rezultatet e konsultimit, grupet e prekura, burimet e të dhënave, kostot në lekë…",
)
uploaded = st.file_uploader(
    "Dokument publik mbështetës (opsional; PDF ose DOCX)",
    type=["pdf", "docx"], key="ria_public_file",
)
excerpt = ""
if uploaded:
    checked = screen_upload(
        uploaded.name, uploaded.getvalue(),
        public_legal=True, max_chars=120000,
    )
    if checked.blocked:
        st.error(upload_block_message(checked.reason))
        st.stop()
    if checked.warning:
        st.warning(checked.warning)
    if checked.text.strip():
        digest = hashlib.sha256(uploaded.getvalue()).hexdigest()[:10]
        with st.expander("Lexo tekstin e nxjerrë nga dokumenti"):
            st.text_area(
                "Teksti i lexuar", value=checked.text,
                key="ria_full_upload_" + digest, disabled=True, height=220,
            )
        excerpt = st.text_area(
            "Zgjidh fragmentin për VN-në (maksimumi 3,000 shenja)",
            value=checked.text[:3000],
            max_chars=3000, key="ria_upload_excerpt_" + digest,
            height=135,
        )
        if len(checked.text) > 3000:
            st.caption(
                "Dokumenti është më i gjatë. Përzgjidhni fragmentin përkatës; "
                "pjesa tjetër nuk përdoret automatikisht."
            )

metadata = {
    "title": title.strip(), "ministry": ministry.strip(),
    "phase": phase, "origin": origin, "eu_act": eu_act.strip(),
    "strategies": "", "consultation_date": "", "assessment_date": "",
    "pm_review": "", "ria_number": "", "contact": "",
}
evidence = context.strip() + (
    "\n\nFRAGMENT DOKUMENTI PUBLIK:\n" + excerpt.strip()
    if excerpt.strip() else ""
)
if len(evidence) > 10500:
    st.warning("Materiali dhe fragmenti së bashku duhet të kenë maksimumi 10,500 shenja.")
if scan_text_fields(context, options, consultation, excerpt, public_legal=True).blocked:
    st.error(BLOCK_NOTICE)
    st.stop()

st.markdown("**3. Hartimi sipas Shtojcës 2**")
section = st.selectbox(
    "Zgjidh seksionin", list(RIA_SECTIONS),
    format_func=lambda key: RIA_SECTIONS[key][0],
    key="ria_current_section",
)
st.caption(
    "Raporti hartohet seksion pas seksioni për të shmangur përgjigjet "
    "e përgjithshme dhe llogaritjet e sajuara."
)

# Do not clear approved/edited sections just because the user changes the UI.
drafts = st.session_state.setdefault("ria_section_drafts", {})
if st.button("Generate RIA section", type="primary", key="ria_generate"):
    if not title.strip() or not evidence.strip():
        st.warning("Plotësoni emërtimin dhe të dhënat faktike për nismën.")
    else:
        try:
            messages = build_ria_messages(
                section=section, metadata=metadata, evidence=evidence,
                options=options, consultation=consultation,
                previous="\n".join(
                    f"{RIA_SECTIONS[key][0]}: {value[:350]}"
                    for key, value in drafts.items() if key != section
                )[:2000],
            )
            with st.spinner("Po hartohet seksioni i VN-së…"):
                answer = generate_ria_section(
                    messages,
                    str(st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "")).strip(),
                    str(st.secrets.get("CLOUDFLARE_API_TOKEN", "")).strip(),
                )
            if scan_text_fields(answer, public_legal=True).blocked:
                st.error(BLOCK_NOTICE)
            else:
                drafts[section] = answer
                st.session_state["ria_draft_" + section] = answer
        except ValueError as exc:
            st.error(friendly_error(exc))

if section in drafts:
    edited = st.text_area(
        "Drafti i redaktueshëm: " + RIA_SECTIONS[section][0],
        value=drafts[section], key="ria_draft_" + section, height=370,
    )
    drafts[section] = edited
    st.caption("Redaktimet ruhen në këtë sesion të aplikacionit; shkarkoni Word për ruajtje.")

st.markdown(f"**Seksione të plotësuara: {len(drafts)}/{len(RIA_SECTIONS)}**")
if drafts:
    st.download_button(
        "Download RIA draft (Word)",
        data=report_docx(metadata, drafts),
        file_name="ALBA_RIA_draft.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="ria_download_docx", on_click="ignore",
    )
    st.caption(
        "Përmbledhja, analiza dhe tabelat e Shtojcës 2/a–2/b "
        "mbeten draft për plotësim dhe verifikim me evidenca reale."
    )
