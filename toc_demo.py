"""Separate Streamlit proof of concept, not the public ALBA 3.1 app."""
import streamlit as st
from toc_builder import extract_document, split_provisions, to_word

st.set_page_config(page_title="ALBA – Word ToC prototype", layout="wide")
st.title("ALBA – Word ToC Builder (prototype)")
st.warning(
    "Experimental, separate from ALBA 3.1. Only public or synthetic texts. "
    "No personal data, confidential files or internal GIZ documents. "
    "No assessment of legal approximation or transposition."
)
st.write(
    "Upload a text-based PDF or DOCX directive. This prototype extracts "
    "Article/Annex sections and prepares a Word table. Paragraphs and "
    "lettered points stay within their parent article pending manual review."
)
upload = st.file_uploader("EU directive or synthetic example", type=["pdf", "docx"])
safe = st.checkbox("I confirm the file is public or synthetic and non-confidential.")
if upload is not None and safe:
    try:
        extracted = extract_document(upload.name, upload.getvalue())
        rows = split_provisions(extracted.text)
        st.metric("Word ToC rows", len(rows))
        for warning in extracted.warnings:
            st.warning(warning)
        if len(rows) == 1 and rows[0].reference.startswith("Unstructured"):
            st.error("No Article/Annex headings detected. Review source manually.")
        st.dataframe(
            [{"EU provision": row.reference, "Extracted characters": len(row.text)}
             for row in rows],
            hide_index=True,
        )
        with st.expander("Preview first provision"):
            st.text(rows[0].text[:3000])
        data = to_word(rows, upload.name)
        st.download_button(
            "Download draft ToC in Word (.docx)",
            data=data,
            file_name="ALBA_ToC_DRAFT.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        st.info(
            "Check every provision against the original. Missing auto-numbered "
            "Word lists, footnotes or textless PDF pages require manual attention. "
            "This tool does not translate or populate national-law columns."
        )
    except ValueError as exc:
        st.error(str(exc))
elif upload is not None:
    st.info("Confirm that the file is safe before processing.")
