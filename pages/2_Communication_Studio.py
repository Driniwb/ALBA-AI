"""ALBA 3.3 Communication Studio — standalone multipage Streamlit entrypoint.

Only public/synthetic briefs. Cloudflare receives selected source text only
on explicit Generate action. No invented institution approvals or publishing.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from privacy_guard import BLOCK_NOTICE_SQ, combine_safe_text, scan_text_fields, screen_upload

from communication_studio import (
    FORMATS,
    applicable_rules,
    build_messages,
    extract_publishable_text,
    generate_communication,
    load_library,
    qa_flags,
)

st.set_page_config(
    page_title="ALBA AI – Communication Studio",
    page_icon="📣",
    layout="wide",
)
st.title("ALBA AI – Communication Studio")
st.caption("ALBA 3.3 · Komunikim institucional dhe publik në shqip")
st.warning(
    "Prototip editorial. Përdorni vetëm të dhëna publike ose sintetike. "
    "Mos ngarkoni informacione të brendshme, konfidenciale apo personale. "
    "Kur klikoni 'Gjenero', teksti dërgohet te Cloudflare Workers AI."
)

@st.cache_data(show_spinner=False)
def cached_library():
    return load_library()

try:
    sources, rules, albanian = cached_library()
except (OSError, ValueError, KeyError) as exc:
    st.error("Biblioteka e komunikimit nuk mund të lexohet: " + str(exc))
    st.stop()

by_source = {s["source_id"]: s for s in sources}
with st.sidebar:
    st.header("Communication references")
    st.metric("Rregulla të komunikimit", len(rules))
    st.metric("Burime publike", len(sources))
    st.caption(
        "C01–C30 janë sinteza editoriale të ALBA-s të mbështetura në burime "
        "publike, jo udhëzime të autorizuara të institucioneve për ALBA-n. "
        "Rregullat e shqipes R01–R45 zbatohen si orientime gjuhësore."
    )
    with st.expander("Burimet e komunikimit"):
        for row in sources:
            st.markdown(
                "**" + row["source_id"] + " – " + row["institution"] + "**"
            )
            st.caption(row["usage_scope"])
            st.link_button("Shiko burimin", row["url"])

if "comm_mode" not in st.session_state:
    st.session_state["comm_mode"] = "create"
if "comm_source" not in st.session_state:
    st.session_state["comm_source"] = ""

GROUPS = ["Press & Media", "Newsletter & Web", "Social Media"]
group = st.selectbox("1. Kategoria", GROUPS, key="comm_group")
formats = [
    f for f, item in FORMATS.items() if item["group"] == group
]
format_id = st.selectbox(
    "2. Formati",
    formats,
    format_func=lambda f: FORMATS[f]["label"],
    key="comm_target_format",
)
mode = st.radio(
    "3. Lloji i asistencës",
    ["create", "review", "adapt"],
    format_func=lambda x: {
        "create": "Krijo material të ri",
        "review": "Rishiko draftin",
        "adapt": "Përshtat për platformën e zgjedhur",
    }[x],
    horizontal=True,
    key="comm_mode",
)
st.caption(
    "Në modalitetin 'Krijo' jepni fakte të konfirmuara. Për 'Rishiko' "
    "ose 'Përshtat' vendosni draftin ekzistues."
)

col1, col2 = st.columns(2)
with col1:
    organization = st.text_input(
        "Organizata (opsionale)", max_chars=140, key="comm_organization",
    )
    objective = st.text_input(
        "Qëllimi / mesazhi kryesor (opsional)",
        max_chars=240,
        key="comm_objective",
    )
with col2:
    audience = st.text_input(
        "Audienca (opsionale)",
        max_chars=160,
        key="comm_audience",
    )
    tone = st.selectbox(
        "Toni",
        [
            "Profesional dhe i qartë",
            "Institucional dhe neutral",
            "I thjeshtë dhe i afërt me publikun",
        ],
        key="comm_tone",
    )
st.text_area(
    "4. Materiali bazë (fakte të verifikuara ose drafti ekzistues)",
    height=230,
    max_chars=8000,
    placeholder=(
        "P.sh. Në datën [e konfirmuar], institucioni [i konfirmuar] "
        "organizoi ... Përdorni vetëm faktet që mund të publikohen."
    ),
    key="comm_source",
)
supporting_file = st.file_uploader(
    "5. Bashkëlidhni dokument mbështetës (opsional: TXT, MD, DOCX, PDF me tekst)",
    type=["txt", "md", "docx", "pdf"],
    key="comm_supporting_file",
    help=(
        "Dokumenti kontrollohet lokalisht për të dhëna sensitive. "
        "Skedarët e skanuar, me imazhe ose që nuk mund të kontrollohen bllokohen."
    ),
)

visual = st.text_area(
    "Përshkrimi i fotografisë / videos (opsional, veçanërisht për Instagram)",
    height=80,
    max_chars=1000,
    placeholder="Shkruani vetëm atë që shfaqet realisht në materialin vizual.",
    key="comm_visual",
)
safe = st.checkbox(
    "Konfirmoj që materiali është publik ose sintetik, pa të dhëna "
    "personale apo konfidenciale.",
    key="comm_safe",
)

matching = applicable_rules(format_id, rules)
c_rules = [r["rule_id"] for r in matching]
with st.expander("Rregullat aktive për këtë format"):
    st.caption(
        "Rregulla ALBA për komunikimin: "
        + ", ".join(c_rules)
        + ". Standardi i shqipes dhe kontrolli faktik zbatohen veçmas."
    )
    for item in matching:
        st.markdown("**" + item["rule_id"] + "** — " + item["guidance_sq"])
    source_ids = sorted(
        {sid for rule in matching for sid in rule["source_ids"].split("|")}
    )
    st.caption("Burimet mbështetëse: " + ", ".join(
        by_source[s]["institution"] for s in source_ids
    ))

# Scan source text, context fields and the attached document BEFORE
# any AI call or displaying a previously generated result.
uploaded_text = ""
upload_digest = ""
upload_check = (
    screen_upload(supporting_file.name, supporting_file.getvalue(), max_chars=7000)
    if supporting_file is not None else None
)
if scan_text_fields(
    st.session_state["comm_source"], organization, audience, objective, visual
).blocked or (upload_check and upload_check.blocked):
    st.error(BLOCK_NOTICE_SQ)
    st.stop()
if upload_check:
    uploaded_text = upload_check.text
    upload_digest = hashlib.sha256(supporting_file.getvalue()).hexdigest()[:20]
    st.caption("Dokumenti kaloi kontrollin lokal; përmbajtja nuk shfaqet.")
try:
    combined_source = combine_safe_text(
        st.session_state["comm_source"], uploaded_text, max_chars=8000
    )
except ValueError as exc:
    st.error(str(exc))
    st.stop()

payload_state = {
    "format": format_id,
    "mode": mode,
    "source": combined_source,
    "upload_digest": upload_digest,
    "organization": organization,
    "audience": audience,
    "objective": objective,
    "tone": tone,
    "visual": visual,
}
fingerprint = hashlib.sha256(
    json.dumps(payload_state, sort_keys=True, ensure_ascii=False).encode()
).hexdigest()

if st.button("Gjenero materialin", type="primary"):
    if not safe:
        st.warning("Konfirmoni që materiali është publik ose sintetik.")
    elif not combined_source.strip():
        st.warning("Jepni materiale faktike ose draftin që duhet redaktuar.")
    else:
        try:
            token = st.secrets.get("CLOUDFLARE_API_TOKEN", "").strip()
            account = st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        except Exception:
            token, account = "", ""

        if not token or not account:
            st.error(
                "Mungojnë kredencialet e Cloudflare në Streamlit Secrets."
            )
        else:
            try:
                messages = build_messages(
                    format_id=format_id,
                    mode=mode,
                    source_text=combined_source,
                    organization=organization,
                    audience=audience,
                    objective=objective + "\nToni i kërkuar: " + tone,
                    visual_description=visual,
                    communication_rules=rules,
                    albanian_rules=albanian,
                )
                with st.spinner("Po hartohet materiali në shqip..."):
                    output = generate_communication(messages, account, token)
                if scan_text_fields(output).blocked:
                    st.session_state.pop("comm_editor", None)
                    st.session_state.pop("comm_result_fingerprint", None)
                    st.error(BLOCK_NOTICE_SQ)
                    st.stop()
                st.session_state["comm_editor"] = output
                st.session_state["comm_result_fingerprint"] = fingerprint
            except ValueError as exc:
                st.error(str(exc))

if scan_text_fields(st.session_state.get("comm_editor", "")).blocked:
    st.session_state.pop("comm_editor", None)
    st.session_state.pop("comm_result_fingerprint", None)
    st.error(BLOCK_NOTICE_SQ)
    st.stop()

if (
    st.session_state.get("comm_result_fingerprint") == fingerprint
    and st.session_state.get("comm_editor")
):
    st.divider()
    st.subheader("Materiali i përgatitur")
    st.text_area(
        "Teksti i redaktueshëm (mund ta ndryshoni para publikimit)",
        key="comm_editor",
        height=340,
    )
    draft = st.session_state["comm_editor"]
    if scan_text_fields(draft).blocked:
        st.session_state.pop("comm_editor", None)
        st.error(BLOCK_NOTICE_SQ)
        st.stop()
    extracted = extract_publishable_text(draft)
    if extracted:
        with st.expander("Shiko përmbajtjen për publikim"):
            st.markdown(extracted)
    flags = qa_flags(combined_source, draft, format_id)
    if flags:
        st.warning("Kontrolle editoriale që kërkojnë shqyrtim:")
        for flag in flags:
            st.write("• " + flag)
    else:
        st.info(
            "Kontrollet automatike nuk gjetën sinjalizime. "
            "Kjo nuk konfirmon faktet, terminologjinë ose miratimin e publikimit."
        )
    if format_id == "x" and extracted:
        st.caption(
            f"Gjatësia orientuese e postimit X: {len(extracted)} / 280 "
            "karaktere (URL-të mund të numërohen ndryshe nga X)."
        )

    download_text = extracted if extracted else draft
    st.download_button(
        "Shkarko tekstin (.txt)",
        data=download_text,
        file_name="ALBA_Communication_Studio_DRAFT.txt",
        mime="text/plain; charset=utf-8",
    )

    def prepare_adaptation():
        publishable = extract_publishable_text(st.session_state["comm_editor"])
        proposed = publishable or st.session_state["comm_editor"]
        if scan_text_fields(proposed).blocked:
            st.session_state["comm_editor"] = ""
            st.session_state["comm_result_fingerprint"] = ""
            return
        st.session_state["comm_source"] = proposed
        st.session_state["comm_mode"] = "adapt"
        st.session_state["comm_editor"] = ""
        st.session_state["comm_result_fingerprint"] = ""

    st.button(
        "Përdore si bazë për një platformë tjetër",
        on_click=prepare_adaptation,
        help="Vendos këtë tekst si material burimor dhe zgjidh një format tjetër.",
    )
elif st.session_state.get("comm_editor"):
    st.info(
        "Ndryshuat formatin ose materialin. Klikoni 'Gjenero materialin' "
        "për të krijuar një version të ri."
    )
