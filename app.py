"""ALBA 2.0 — one Streamlit entrypoint, one visible conversational workspace.

The previous specialist scripts remain in the repository for future internal
integration. They are deliberately NOT registered as pages, so Streamlit
cannot expose the legacy navigation or direct tool page URLs in this app.
This branch does not alter the existing main deployment.
"""
import streamlit as st

st.set_page_config(
    page_title="ALBA 2.0",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown(
        '<div class="alba-brand">'
        '<span class="alba-brand-mark">A</span>'
        '<span><span class="alba-brand-name">ALBA</span>'
        '<span class="alba-brand-caption">Legal workspace · v2.0</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )

# Register ONLY the chat. No Writing Assistant, ToC, Drafting, RIA, or
# Reporting links can appear in Streamlit's navigation, even on direct URLs.
workspace = st.Page(
    "pages/5_Chat_Workspace.py",
    title="ALBA",
    icon=":material/chat:",
    default=True,
    url_path="",
)
st.navigation([workspace], position="hidden").run()
