"""ALBA Streamlit entrypoint: named navigation plus Chat Workspace.

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
    st.caption("Chat · Writing · Concordance · Legal drafting · Communication · EU reporting")

pages = [
    st.Page(
        "pages/5_Chat_Workspace.py",
        title="Chat Workspace",
        icon=":material/forum:",
        default=True,
    ),
    st.Page(
        "writing_assistant.py",
        title="Writing Assistant",
        icon=":material/edit_document:",
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
    st.Page(
        "pages/3_Legal_Drafting.py",
        title="Legal Drafting",
        icon=":material/gavel:",
    ),
    st.Page(
        "pages/4_EU_Reporting.py",
        title="EU Communication & Reporting",
        icon=":material/account_balance:",
    ),
]

selected = st.navigation(pages)
selected.run()
