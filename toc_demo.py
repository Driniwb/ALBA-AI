"""Separate Streamlit PoC: directive PDF/DOCX + user-supplied blank ToC DOCX."""
import streamlit as st
from toc_builder import extract_document
from toc_units import first_n_articles
from toc_template import create_toc_using_template

st.set_page_config(page_title="ALBA – ToC Word preview", layout="wide")
st.title("ALBA – ToC Builder (Word preview)")
st.warning(
    "Technical prototype, separate from ALBA 3.1. Upload only public or "
    "synthetic source documents and a non-confidential BLANK ToC template. "
    "Do not upload internal drafts or completed ToCs with sensitive data."
)
st.write(
    "Upload a public text-based PDF or Word directive and a blank seven-column "
    "Albanian ToC in Word. The resulting Word file carries only the "
    "EU provision reference and extracted EU wording; national references, "
    "content, compliance and Remarks are left blank."
)

directive = st.file_uploader(
    "1. Direktiva (PDF me tekst ose .docx)", type=["pdf", "docx"],
    key="directive",
)
template = st.file_uploader(
    "2. Modeli bosh ToC me 7 kolona (.docx)", type=["docx"],
    key="toc_template",
)
title = st.text_input("Emërtimi i direktivës", value="Direktiva 2008/68/KE")
n_articles = st.selectbox("Numri i neneve për provën", [1, 2, 3, 4, 5, 6, 7, 8], index=2)
safe = st.checkbox(
    "Konfirmoj që dokumentet janë publike ose sintetike dhe nuk janë konfidenciale."
)

if directive is not None and template is not None and safe:
    try:
        extracted = extract_document(directive.name, directive.getvalue())
        units = first_n_articles(extracted.text, n_articles)
        st.metric("Rreshta me dispozita të BE-së", len(units))
        for warning in extracted.warnings:
            st.warning(warning)
        st.dataframe(
            [{"Neni": unit.reference, "Karaktere": len(unit.text)} for unit in units],
            hide_index=True,
        )
        with st.expander("Kontrollo tekstin e nxjerrë (rreshti i parë)"):
            st.text(units[0].text[:3000])
        result = create_toc_using_template(
            template.getvalue(), units, title.strip()
        )
        st.download_button(
            "Shkarko ToC në Word sipas modelit",
            data=result,
            file_name="ALBA_ToC_7_kolona_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        st.info(
            "Kjo është një tabelë e nxjerrë teknikisht, jo transkriptim i "
            "verifikuar. Kontrollo çdo nen, pikë, shkronjë dhe aneks me "
            "botimin autentik. Ndarja e fjalive veçmas dhe vlerësimi "
            "F/P/N/N/A kërkojnë ekspert."
        )
    except (ValueError, AssertionError) as exc:
        st.error(str(exc))
elif directive is not None or template is not None:
    st.info("Ngarko të dy dokumentet dhe konfirmo kushtet e përdorimit.")
