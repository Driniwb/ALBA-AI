"""ALBA Streamlit entrypoint: named navigation for three writing tools.

This file is intentionally a lightweight router. The first sidebar page is
called 'Writing Assistant', not 'app' or 'ALBA AI'. All existing functionality
is implemented by the selected page scripts.
"""
import streamlit as st

st.set_page_config(
    page_title="ALBA",
    page_icon="📗",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown("## ALBA")
    st.caption("Writing · Concordance · Communication")

pages = [
    st.Page(
        "writing_assistant.py",
        title="Writing Assistant",
        icon=":material/edit_document:",
        default=True,
    ),
    st.Page(
        "pages/1_ToC_Builder.py",
        title="ToC Builder",
        icon=":material/table_chart:",
    ),
    st.Page(
        "pages/2_Communication_Studio.py",
        title="Communication Studio",
        icon=":material/campaign:",
    ),
]

selected = st.navigation(pages)
selected.run()
