"""ALBA 2.0 entrypoint: a single visible workspace with hidden legacy tools.

Specialist tool pages remain registered for compatibility, but the public
navigation is Project and Chat oriented inside the default workspace.
"""
import streamlit as st
from alba_features import COMMUNICATION_STUDIO_VISIBLE

st.set_page_config(
    page_title="ALBA",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown(
        '<div class="alba-brand">'
        '<span class="alba-brand-mark">A</span>'
        '<span><span class="alba-brand-name">ALBA</span>'
        '<span class="alba-brand-caption">Legal workspace</span></span>'
        '</div>',
        unsafe_allow_html=True,
    )

pages = [
    st.Page(
        "pages/5_Chat_Workspace.py",
        title="Legal Assistant",
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
    *([
        st.Page(
            "pages/2_Communication_Studio.py",
            title="Communication Studio",
            icon=":material/campaign:",
        )
    ] if COMMUNICATION_STUDIO_VISIBLE else []),
    st.Page(
        "pages/3_Legal_Drafting.py",
        title="Legal Drafting",
        icon=":material/gavel:",
    ),
    st.Page(
        "pages/6_RIA_Builder.py",
        title="RIA Builder",
        icon=":material/assignment:",
    ),
    st.Page(
        "pages/4_EU_Reporting.py",
        title="EU Communication & Reporting",
        icon=":material/account_balance:",
    ),
]

# Keep specialist pages registered for internal routing only.
# The sidebar belongs to Projects and Chats.
selected = st.navigation(pages, position="hidden")
selected.run()
