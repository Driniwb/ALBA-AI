"""ALBA's mid-century retro-futurist visual system.

Inspired by atomic-age editorial signage and analogue control panels, such
as those seen in the Fallout TV production design, WITHOUT copying visual
assets, logos, proprietary fonts or in-show iconography. Built from CSS only.
Application data and privacy handling are unaffected.
"""
import streamlit as st

_CSS = """
<style>
:root {
  /* Aged-ivory, brass, teal and deep forest: analogue retro-future. */
  --alba-night: #161d1a;
  --alba-ink: #1d2926;
  --alba-control: #29372f;
  --alba-teal: #608f82;
  --alba-mint: #a9c9b4;
  --alba-ivory: #f4eedb;
  --alba-amber: #e3ac57;
  --alba-rust: #bf7451;
  --alba-border: rgba(222,207,164,.29);
}

[data-testid="stAppViewContainer"] {
    background:
      radial-gradient(ellipse at 86% 0%, rgba(159,172,123,.12), transparent 38%),
      repeating-linear-gradient(0deg, transparent 0 35px,
        rgba(244,238,219,.009) 36px 37px),
      linear-gradient(160deg, #1b2924 0%, #161d1a 85%);
}
[data-testid="stHeader"] {background: rgba(22,29,26,.85);}
[data-testid="stSidebar"] {
    background:
      radial-gradient(circle at -30% 88%, rgba(227,172,87,.1), transparent 38%),
      linear-gradient(165deg, #33433a 0%, #1b2925 50%, #141d19 100%);
    border-right: 1px solid var(--alba-border);
}
[data-testid="stSidebar"]::after {
    /* Decorative offset mechanical ring at the foot of the sidebar. */
    content: "";
    display: block;
    position: absolute;
    right: -94px;
    bottom: 17px;
    width: 206px;
    height: 206px;
    border-radius: 50%;
    border: 13px solid rgba(227,172,87,.33);
    box-shadow:
        inset 0 0 0 10px rgba(22,29,26,.72),
        inset 0 0 0 13px rgba(169,201,180,.24),
        0 0 0 6px rgba(244,238,219,.07);
    pointer-events: none;
    opacity: .66;
}
[data-testid="stSidebarNav"] a {
    border: 1px solid transparent;
    border-radius: 9px;
    transition: background .16s ease, border-color .16s ease;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(244,238,219,.065);
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: rgba(227,172,87,.1);
    border: 1px solid rgba(227,172,87,.31);
    box-shadow: inset 3px 0 0 var(--alba-amber);
}
[data-testid="stSidebar"] h2 {
    font-family: Georgia, "Times New Roman", serif;
    font-weight: 700;
    font-size: 2.1rem;
    letter-spacing: .055em;
    color: var(--alba-ivory);
}
[data-testid="stMainBlockContainer"] {
    padding-top: 1.7rem;
    max-width: 1140px;
}
h1,h2,h3 {letter-spacing: -.018em; color: var(--alba-ivory);}
h1 {
    font-family: Georgia, 'Times New Roman', serif;
    font-weight: 700;
}
h2,h3 {font-weight: 660;}
p,li {line-height: 1.55;}
a {color: var(--alba-mint);}
[data-testid="stMetric"] {
    border: 1px solid var(--alba-border);
    border-radius: 12px;
    padding: 14px 18px;
    background: linear-gradient(155deg, #34463a, #25332c);
    box-shadow: inset 0 1px 0 rgba(244,238,219,.1), 0 3px 12px rgba(0,0,0,.12);
}
[data-testid="stFileUploader"],
[data-testid="stExpander"] {
    border: 1px solid var(--alba-border);
    border-radius: 12px;
    background: rgba(41,55,47,.28);
}
[data-testid="stTextArea"] textarea,
[data-testid="stTextInput"] input,
[data-baseweb="select"] > div {
    border-radius: 9px;
    border-color: rgba(169,201,180,.29);
}
[data-testid="stTextArea"] textarea:focus,
[data-testid="stTextInput"] input:focus {
    border-color: var(--alba-amber);
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: var(--alba-amber);
    color: #21251c;
    border: 1px solid #f1c77d;
    border-radius: 9px;
    font-weight: 710;
    letter-spacing: .012em;
    box-shadow: 0 2px 0 #986a33;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: #f1c47b;
    color: #21251c;
    border-color: #ffe3a8;
}
.stButton > button,
.stDownloadButton > button {
    border-radius: 9px;
    transition: background .14s ease, border-color .14s ease;
}
[data-testid="stAlert"] {border-radius: 10px;}
/* Key element: an architectural dashboard header, NOT a game HUD. */
.alba-hero {
    position: relative;
    isolation: isolate;
    overflow: hidden;
    border: 1px solid rgba(227,172,87,.44);
    border-radius: 17px;
    min-height: 136px;
    padding: 27px 32px 24px;
    margin: 0 0 1.45rem;
    background:
        linear-gradient(90deg, rgba(227,172,87,.15), transparent 31%),
        repeating-linear-gradient(0deg, transparent 0 14px,
            rgba(244,238,219,.015) 15px 16px),
        linear-gradient(118deg, #334c43 0%, #22322d 54%, #17221e 100%);
    box-shadow: inset 0 1px 0 rgba(244,238,219,.13),
                0 9px 22px rgba(0,0,0,.16);
}
.alba-hero::before {
    content: "";
    position: absolute;
    left: 12px;
    top: 13px;
    bottom: 13px;
    width: 3px;
    border-radius: 3px;
    background: linear-gradient(var(--alba-ivory), var(--alba-amber), var(--alba-rust));
    opacity: .75;
}
.alba-hero::after {
    /* A concentric chrome-and-brass dial, echoing analogue instruments. */
    content: "";
    position: absolute;
    width: 238px;
    height: 238px;
    right: -33px;
    top: -91px;
    border-radius: 50%;
    border: 14px solid rgba(238,222,181,.72);
    box-shadow:
        inset 0 0 0 10px rgba(37,57,50,.95),
        inset 0 0 0 12px rgba(227,172,87,.84),
        inset 0 0 0 27px rgba(95,145,130,.18),
        inset 0 0 0 29px rgba(238,222,181,.38),
        0 0 0 7px rgba(227,172,87,.12);
    pointer-events: none;
    opacity: .78;
}
.alba-overline {
    position: relative;
    z-index: 1;
    color: var(--alba-ivory);
    text-transform: uppercase;
    letter-spacing: .165em;
    font-size: .81rem;
    font-weight: 770;
    max-width: calc(100% - 162px);
}
.alba-stripes {
    position: relative;
    z-index: 1;
    height: 6px;
    width: 163px;
    border-radius: 8px;
    margin: 15px 0 0;
    background: linear-gradient(90deg,
        #f4eedb 0 26%, #a9c9b4 26% 51%,
        #608f82 51% 76%, #e3ac57 76% 100%);
}
.alba-hero-mini {
    position: relative;
    z-index: 1;
    display: inline-block;
    margin-top: 11px;
    color: rgba(244,238,219,.69);
    font-family: Georgia, "Times New Roman", serif;
    font-style: italic;
    font-size: .85rem;
    letter-spacing: .016em;
}
@media (max-width: 720px) {
    .alba-hero {min-height: 116px; padding: 18px 19px 18px 25px;}
    .alba-hero::after {right: -159px; top: -100px; opacity: .35;}
    .alba-overline {max-width: 94%; font-size: .73rem; letter-spacing: .12em;}
    [data-testid="stSidebar"]::after {opacity: .2;}
}
@media (prefers-reduced-motion: reduce) {
    .stButton > button, [data-testid="stSidebarNav"] a {
        transition: none;
    }
}
</style>
"""


def apply_theme(section: str = "WORKSPACE") -> None:
    """Inject shared styling; fixed markup only; no user data in HTML."""
    st.markdown(_CSS, unsafe_allow_html=True)
    section_label = {
        "EDITOR": "WRITING ASSISTANT",
        "TOC": "TABLE OF CONCORDANCE",
        "COMM": "COMMUNICATION STUDIO",
    }.get(section, "WORKSPACE")
    st.markdown(
        '<div class="alba-hero"><div class="alba-overline">'
        'ALBA / ' + section_label
        + '</div><div class="alba-stripes" aria-hidden="true"></div>'
        '<div class="alba-hero-mini">Language, made precise.</div></div>',
        unsafe_allow_html=True,
    )
