"""Shared ALBA visual language for all Streamlit pages.

Design: a modern editorial interface using Luap's 2 Bit Matrix palette
(https://lospec.com/palette-list/2-bit-matrix) with a restrained
warm terracotta accent inspired by 1970s–1980s print design.
Styling only; no application logic, file access or external assets.
"""
import streamlit as st

_CSS = """
<style>
:root {
  --alba-dark: #0d1a1a;
  --alba-panel: #142923;
  --alba-forest: #203a32;
  --alba-mint: #add9bc;
  --alba-white: #f2fff2;
  --alba-sage: #5b8c7c;
  --alba-amber: #d57847;
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(ellipse at 95% 0%, rgba(91,140,124,.14) 0%, transparent 35%),
      var(--alba-dark);
}
[data-testid="stSidebar"] {
    background: linear-gradient(170deg, #10231e, #0d1a1a 82%);
    border-right: 1px solid rgba(173,217,188,.23);
}
[data-testid="stHeader"] {background: rgba(13,26,26,.72); }
[data-testid="stMainBlockContainer"] {
    padding-top: 2.4rem;
    max-width: 1120px;
}
h1,h2,h3 {
    letter-spacing: -.025em;
    color: var(--alba-white);
}
h1 {
    font-family: Georgia, 'Times New Roman', serif;
    font-weight: 650;
}
h2,h3 {font-weight: 660;}
p,li {line-height: 1.57;}
a {color: var(--alba-mint);}
[data-testid="stMetric"] {
    border: 1px solid rgba(173,217,188,.17);
    border-radius: 14px;
    padding: 14px 18px;
    background: rgba(20,41,35,.8);
}
[data-testid="stFileUploader"],
[data-testid="stExpander"] {
    border: 1px solid rgba(173,217,188,.17);
    border-radius: 14px;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--alba-amber);
    color: var(--alba-dark);
    border: 0;
    border-radius: 10px;
    font-weight: 650;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: #e39b6f;
    color: var(--alba-dark);
    border: 0;
}
.stButton > button,
.stDownloadButton > button {
    border-radius: 10px;
    transition: border-color .12s ease, background-color .12s ease;
}
[data-testid="stAlert"] {border-radius: 12px;}
.alba-overline {
    color: var(--alba-mint);
    text-transform: uppercase;
    letter-spacing: .15em;
    font-size: .75rem;
    font-weight: 700;
    margin: .45rem 0 .1rem;
}
.alba-stripes {
    height: 5px;
    width: 134px;
    margin-top: -.2rem;
    margin-bottom: 1.35rem;
    border-radius: 8px;
    background: linear-gradient(90deg,
       #f2fff2 0 25%, #add9bc 25% 50%,
       #5b8c7c 50% 75%, #d57847 75% 100%);
}
.alba-description {
    color: #d5ead9;
    font-size: .96rem;
    max-width: 64rem;
}
</style>
"""


def apply_theme(section: str = "WORKSPACE") -> None:
    """Inject consistent style; no user data is rendered into HTML."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="alba-overline">ALBA AI / '
        + {"EDITOR": "WRITING ASSISTANT",
           "TOC": "TABLE OF CONCORDANCE",
           "COMM": "COMMUNICATION STUDIO"}.get(section, "WORKSPACE")
        + '</div><div class="alba-stripes" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
