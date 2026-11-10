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
/* Restrained 70s editorial sweep: decorative CSS, no image request/tracking. */
[data-testid="stSidebar"]::after {
    content: "";
    display: block;
    position: absolute;
    left: -82px;
    bottom: 28px;
    width: 220px;
    height: 105px;
    border-radius: 0 90px 90px 0;
    border-top: 8px solid rgba(242,255,242,.58);
    box-shadow: 0 -13px 0 -5px rgba(173,217,188,.7),
                0 -27px 0 -19px rgba(213,120,71,.85);
    transform: rotate(-8deg);
    pointer-events: none;
    opacity: .65;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    border-left: 3px solid #d57847;
    border-radius: 9px;
    background: rgba(173,217,188,.13);
}
[data-testid="stSidebar"] h2 {
    font-family: Georgia, "Times New Roman", serif;
    font-weight: 700;
    letter-spacing: .035em;
    color: #f2fff2;
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
/* Main hero with offset ribbon arches, inspired by the supplied mockup. */
.alba-hero {
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(173,217,188,.25);
    border-radius: 20px;
    min-height: 102px;
    padding: 23px 28px 19px;
    margin: 0 0 1.5rem;
    background:
        radial-gradient(ellipse at 85% -15%, rgba(91,140,124,.2), transparent 50%),
        linear-gradient(120deg, #182b24, #0d1a1a 87%);
}
.alba-hero::after {
    content: "";
    position: absolute;
    width: 275px;
    height: 160px;
    right: -40px;
    top: -106px;
    border: 12px solid rgba(242,255,242,.86);
    border-radius: 0 0 0 110px;
    box-shadow: -16px 16px 0 -2px rgba(213,120,71,.92),
                -33px 33px 0 -17px rgba(173,217,188,.89);
    transform: rotate(-8deg);
    opacity: .84;
    pointer-events: none;
}
.alba-overline {
    position: relative;
    z-index: 1;
    color: var(--alba-mint);
    text-transform: uppercase;
    letter-spacing: .17em;
    font-size: .76rem;
    font-weight: 740;
    margin-bottom: .35rem;
}
.alba-stripes {
    position: relative;
    z-index: 1;
    height: 5px;
    width: 142px;
    border-radius: 9px;
    margin: 12px 0 0;
    background: linear-gradient(90deg,
        #f2fff2 0 26%, #add9bc 26% 52%,
        #5b8c7c 52% 76%, #d57847 76% 100%);
}
@media (max-width: 720px) {
    .alba-hero { padding: 16px 17px; min-height: 80px; }
    .alba-hero::after { right: -160px; opacity: .36; }
    [data-testid="stSidebar"]::after { opacity: .36; }
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
        '<div class="alba-hero"><div class="alba-overline">ALBA / '
        + {"EDITOR": "WRITING ASSISTANT",
           "TOC": "TABLE OF CONCORDANCE",
           "COMM": "COMMUNICATION STUDIO"}.get(section, "WORKSPACE")
        + '</div><div class="alba-stripes" aria-hidden="true"></div></div>',
        unsafe_allow_html=True,
    )
