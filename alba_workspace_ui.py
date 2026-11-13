"""Minimal EU-law-workspace-inspired visual system for ALBA's single chat view.

Original styling only. This does not add legal-source retrieval or change
document security, data storage, or model functionality.
"""
import streamlit as st

WORKSPACE_CSS = """
<style>
:root {
  --alba-ink: #1e293b;
  --alba-subtle: #617085;
  --alba-paper: #ffffff;
  --alba-sidebar: #f5f7fb;
  --alba-line: #e1e7ef;
  --alba-blue: #2d58a7;
  --alba-blue-hover: #244b91;
  --alba-blue-tint: #eaf0fc;
  --alba-user-bubble: #eef2f7;
}
html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
  background: var(--alba-paper) !important;
  color: var(--alba-ink) !important;
}
[data-testid="stHeader"] {
  background: rgba(255,255,255,.94) !important;
  border-bottom: 1px solid #f1f3f7;
}
[data-testid="stSidebar"] {
  background: var(--alba-sidebar) !important;
  border-right: 1px solid var(--alba-line) !important;
  min-width: 282px;
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: .8rem;
}
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  font-family: Inter, ui-sans-serif, system-ui, Arial, sans-serif !important;
  color: var(--alba-ink) !important;
  font-size: .85rem !important;
  font-weight: 730 !important;
  letter-spacing: .01em !important;
  margin: .4rem 0 .2rem !important;
}
.alba-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 6px 18px;
  margin: 0 0 10px;
  border-bottom: 1px solid var(--alba-line);
}
.alba-brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 36px;
  width: 36px;
  border-radius: 11px;
  color: #fff;
  background: #203b70;
  font-size: 20px;
  font-weight: 750;
  letter-spacing: -.06em;
}
.alba-brand-name {
  font: 750 1.1rem/1.2 Inter, ui-sans-serif, system-ui, sans-serif;
  color: #1d2b47;
  letter-spacing: -.025em;
}
.alba-brand-caption {
  display: block;
  color: var(--alba-subtle);
  font-size: .72rem;
  margin-top: 2px;
  letter-spacing: .015em;
}
[data-testid="stSidebar"] [data-testid="stButton"] button,
[data-testid="stSidebar"] [data-testid="stPopover"] button {
  border-radius: 9px;
  font-weight: 500;
  box-shadow: none !important;
}
[data-testid="stSidebar"] button[kind="secondary"] {
  background: transparent !important;
  color: var(--alba-ink) !important;
  border: 1px solid transparent !important;
}
[data-testid="stSidebar"] button[kind="secondary"]:hover {
  background: #e8edf6 !important;
}
.st-key-alba_new_chat button {
  background: #244b91 !important;
  color: #ffffff !important;
  border: 1px solid #244b91 !important;
  min-height: 42px;
  font-weight: 650 !important;
}
.st-key-alba_new_chat button:hover {
  background: #193b77 !important;
}
.st-key-alba_sidebar_chat_search input {
  background: #fff !important;
  color: var(--alba-ink) !important;
  border: 1px solid #d8e0ec !important;
  border-radius: 9px !important;
  min-height: 39px;
  font-size: .88rem !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: transparent !important;
  border: 0 !important;
  border-radius: 9px !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
  border-radius: 8px !important;
  font-size: .85rem !important;
  font-weight: 580 !important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
  background: #e8edf6 !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: .35rem;
}
[data-testid="stMainBlockContainer"] {
  max-width: 1160px !important;
  padding-top: .9rem !important;
  padding-bottom: 10rem !important;
  color: var(--alba-ink) !important;
}
[data-testid="stMainBlockContainer"] h1,
[data-testid="stMainBlockContainer"] h2,
[data-testid="stMainBlockContainer"] h3,
[data-testid="stMainBlockContainer"] p,
[data-testid="stMainBlockContainer"] li {
  color: var(--alba-ink) !important;
}
.alba-top-title {
  color: #25334b;
  font-size: .94rem;
  font-weight: 720;
  letter-spacing: -.01em;
  padding: 8px 0;
}
.alba-top-subtitle {
  font-size: .74rem;
  font-weight: 450;
  margin-left: 9px;
  color: #8490a1;
}
.alba-welcome-eyebrow {
  color: #2e5b9e !important;
  font-size: .75rem;
  font-weight: 720;
  letter-spacing: .13em;
  text-align: center;
  margin-top: clamp(42px, 12vh, 110px);
}
.alba-welcome-title {
  color: #152943 !important;
  font-size: clamp(2rem, 4vw, 3.1rem);
  letter-spacing: -.045em;
  line-height: 1.15;
  font-weight: 700;
  text-align: center;
  margin: .85rem auto .65rem;
}
.alba-welcome-subtitle {
  color: var(--alba-subtle) !important;
  font-size: .98rem;
  line-height: 1.6;
  max-width: 590px;
  margin: .2rem auto 1.65rem;
  text-align: center;
}
[data-testid="stChatMessage"] {
  max-width: 850px !important;
  margin: 0 auto .65rem !important;
  border: none !important;
  box-shadow: none !important;
  border-radius: 15px !important;
  background: transparent !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  max-width: min(75%, 690px) !important;
  margin-left: auto !important;
  margin-right: max(0px, calc((100% - 850px)/2)) !important;
  border: 1px solid #e3e9f2 !important;
  border-radius: 15px !important;
  background: var(--alba-user-bubble) !important;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
  padding-left: 0 !important;
}
[data-testid="stBottom"] {
  background: linear-gradient(0deg,#fff 75%,rgba(255,255,255,0)) !important;
}
[data-testid="stBottom"] > div {
  max-width: 840px !important;
  margin-left: auto !important;
  margin-right: auto !important;
}
.st-key-alba_chat_empty {
  width: min(100%, 760px);
  margin: 0 auto;
}
[data-testid="stBottom"] [data-testid="stChatInput"],
.st-key-alba_chat_empty [data-testid="stChatInput"] {
  border: 1px solid #ccd6e5 !important;
  border-radius: 17px !important;
  background: #fff !important;
  box-shadow: 0 5px 24px rgba(30,47,84,.07) !important;
}
[data-testid="stChatInput"] textarea {
  color: var(--alba-ink) !important;
  font-size: .95rem !important;
}
[data-testid="stChatInput"] textarea:focus {
  outline-color: #96afe0 !important;
}
[data-testid="stMainBlockContainer"] button[kind="primary"],
[data-testid="stBottom"] button[kind="primary"] {
  background: var(--alba-blue) !important;
  border-color: var(--alba-blue) !important;
  color: white !important;
}
[data-testid="stMainBlockContainer"] button[kind="primary"]:hover {
  background: var(--alba-blue-hover) !important;
}
[data-testid="stMainBlockContainer"] .stButton > button {
  border-radius: 9px;
  box-shadow: none !important;
}
.st-key-alba_sources_panel {
  border-left: 1px solid var(--alba-line) !important;
  padding-left: 1.15rem;
  min-height: 55vh;
}
.alba-source-title {
  color: var(--alba-subtle) !important;
  letter-spacing: .08em;
  font-size: .72rem;
  font-weight: 750;
}
.st-key-alba_sources_panel [data-testid="stLinkButton"] button {
  border: 0 !important;
  color: #24569d !important;
  background: #f2f6fc !important;
  justify-content: flex-start;
  white-space: normal;
  text-align: left;
}
.st-key-alba_followups .stButton > button {
  border-radius: 999px !important;
  color: #304c7a !important;
  border: 1px solid #d7dfeb !important;
  background: #fff !important;
  text-align: left !important;
}
.st-key-alba_followups .stButton > button:hover {
  background: var(--alba-blue-tint) !important;
}
[data-testid="stAlert"] {border-radius: 10px;}
[data-testid="stFileUploader"] {
  border: 1px solid var(--alba-line);
  border-radius: 10px;
}
@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] {padding-top: .5rem !important; padding-bottom: 11rem !important;}
  .alba-top-subtitle {display:none;}
  .alba-welcome-eyebrow {margin-top: 9vh;}
  .alba-welcome-title {font-size: 1.95rem;}
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    max-width: 90% !important;
    margin-right: 0 !important;
  }
  .st-key-alba_sources_panel {min-height: 0; border-left: 0 !important; padding-left: 0;}
}
@media (prefers-reduced-motion: reduce) {
  * {scroll-behavior:auto !important; transition:none !important;}
}
</style>
"""


def apply_workspace_ui() -> None:
    """Apply the single-workspace styling without altering chat behavior."""
    st.markdown(WORKSPACE_CSS, unsafe_allow_html=True)
