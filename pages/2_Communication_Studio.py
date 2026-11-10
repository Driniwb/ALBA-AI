"""ALBA 3.3 Communication Studio — standalone multipage Streamlit entrypoint.

Only public/synthetic briefs. Cloudflare receives selected source text only
on explicit Generate action. No invented institution approvals or publishing.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from privacy_guard import BLOCK_NOTICE, combine_safe_text, scan_text_fields, screen_upload
from ui_copy import friendly_error
from ui_theme import apply_theme

from communication_studio import (
    FORMATS,
    SOCIAL_STYLES,
    generate_social_bundle,
    build_messages,
    extract_publishable_text,
    generate_communication,
    load_library,
    qa_flags,
)

st.set_page_config(
    page_title="ALBA | Communication Studio",
    page_icon="📣",
    layout="wide",
)
apply_theme("COMM")
st.title("Communication Studio")
st.caption("Institutional communications · Albanian-language drafts")
st.warning(
    "Editorial prototype. Use public or synthetic materials only. "
    "Do not enter personal, confidential or internal information."
)

@st.cache_data(show_spinner=False)
def cached_library():
    return load_library()

try:
    sources, rules, albanian = cached_library()
except (OSError, ValueError, KeyError) as exc:
    st.error("The communication library could not be loaded. Please check the application configuration.")
    st.stop()



if "comm_mode" not in st.session_state:
    st.session_state["comm_mode"] = "create"
if "comm_source" not in st.session_state:
    st.session_state["comm_source"] = ""

GROUPS = ["Press & Media", "Newsletter & Web", "Social Media", "EU Communication & Reporting"]
group = st.selectbox("1. Category", GROUPS, key="comm_group")
formats = [
    f for f, item in FORMATS.items() if item["group"] == group
]
format_id = st.selectbox(
    "2. Format",
    formats,
    format_func=lambda f: FORMATS[f]["label"],
    key="comm_target_format",
)
mode = st.radio(
    "3. Type of assistance",
    ["create", "review", "adapt"],
    format_func=lambda x: {
        "create": "Create new content",
        "review": "Review an existing draft",
        "adapt": "Adapt for selected platform",
    }[x],
    horizontal=True,
    key="comm_mode",
)
st.caption(
    "To create, provide verified facts. To review or adapt, paste an existing draft. "
    "Public communications are drafted in Albanian. EU reporting can be in English or Albanian."
)

output_language = "sq"
if group == "EU Communication & Reporting":
    output_language = st.selectbox(
        "4. Reporting language",
        ["en", "sq"], key="comm_eu_language",
        format_func=lambda language: "English" if language == "en" else "Albanian",
    )

style_id = "standard"
if group == "Social Media":
    style_id = st.selectbox(
        "4. Post style",
        options=list(SOCIAL_STYLES),
        format_func=lambda item: SOCIAL_STYLES[item]["label"],
        help=(
            "Elevator pitch prioritises a strong opening, a grounded value "
            "statement and a next step only when the facts support one. "
            "Elevated editorial is more refined and understated."
        ),
        key="comm_post_style",
    )

col1, col2 = st.columns(2)
with col1:
    organization = st.text_input(
        "Organisation (optional)", max_chars=140, key="comm_organization",
    )
    objective = st.text_input(
        "Objective / key message (optional)",
        max_chars=240,
        key="comm_objective",
    )
with col2:
    audience = st.text_input(
        "Target audience (optional)",
        max_chars=160,
        key="comm_audience",
    )
    tone = st.selectbox(
        "Tone",
        [
            "Professional and clear",
            "Institutional and neutral",
            "Accessible and conversational",
        ],
        key="comm_tone",
    )
st.text_area(
    "4. Source material (verified facts or existing draft)",
    height=230,
    max_chars=8000,
    placeholder=(
        "Example: The organisation held a public consultation on [confirmed date]. "
        "Include only facts that are safe to publish."
    ),
    key="comm_source",
)
supporting_file = st.file_uploader(
    "5. Attach supporting document (optional: TXT, MD, DOCX, text-based PDF)",
    type=["txt", "md", "docx", "pdf"],
    key="comm_supporting_file",
    help=(
        "Attachments are screened locally. Scans, images and files that cannot "
        "be checked reliably are blocked."
    ),
)

visual = st.text_area(
    "Photo / video description (optional, especially for Instagram)",
    height=80,
    max_chars=1000,
    placeholder="Describe only what the image or video actually shows.",
    key="comm_visual",
)
safe = st.checkbox(
    "I confirm this material is public or synthetic and contains no personal "
    "or confidential information.",
    key="comm_safe",
)


# Scan source text, context fields and the attached document BEFORE
# any AI call or displaying a previously generated result.
uploaded_text = ""
upload_digest = ""
upload_check = (
    screen_upload(supporting_file.name, supporting_file.getvalue(), max_chars=7000)
    if supporting_file is not None else None
)
if scan_text_fields(
    st.session_state["comm_source"], organization, audience, objective, visual
).blocked or (upload_check and upload_check.blocked):
    st.session_state.pop("comm_editor", None)
    st.session_state.pop("comm_result_fingerprint", None)
    st.session_state.pop("comm_bundle", None)
    st.session_state.pop("comm_bundle_key", None)
    st.error(BLOCK_NOTICE)
    st.stop()
if upload_check:
    uploaded_text = upload_check.text
    upload_digest = hashlib.sha256(supporting_file.getvalue()).hexdigest()[:20]
    st.caption("The attachment passed local screening; its contents are not previewed.")
try:
    combined_source = combine_safe_text(
        st.session_state["comm_source"], uploaded_text, max_chars=8000
    )
except ValueError as exc:
    st.error(friendly_error(exc, context="communication"))
    st.stop()

payload_state = {
    "format": format_id,
    "mode": mode,
    "source": combined_source,
    "upload_digest": upload_digest,
    "organization": organization,
    "audience": audience,
    "objective": objective,
    "tone": tone,
    "style_id": style_id,
    "output_language": output_language,
    "visual": visual,
}
fingerprint = hashlib.sha256(
    json.dumps(payload_state, sort_keys=True, ensure_ascii=False).encode()
).hexdigest()

generate_single = st.button("Generate content", type="primary")
generate_all = (
    st.button(
        "Generate posts for all four platforms",
        help="Uses the same verified source to draft separate Instagram, "
             "LinkedIn, Facebook and X posts in one action.",
    ) if group == "Social Media" else False
)

if generate_single or generate_all:
    if not safe:
        st.warning("Confirm that the material is public or synthetic.")
    elif not combined_source.strip():
        st.warning("Enter verified facts, attach a document, or provide a draft.")
    else:
        try:
            token = st.secrets.get("CLOUDFLARE_API_TOKEN", "").strip()
            account = st.secrets.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
        except Exception:
            token, account = "", ""

        if not token or not account:
            st.error(
                "Cloudflare credentials are missing from the application configuration."
            )
        else:
            try:
                if generate_all:
                    with st.spinner("Preparing four tailored Albanian posts..."):
                        bundle = generate_social_bundle(
                            mode=mode, source_text=combined_source,
                            organization=organization, audience=audience,
                            objective=objective + "\nRequested tone: " + tone,
                            visual_description=visual, style_id=style_id,
                            communication_rules=rules,
                            albanian_rules=albanian, account_id=account,
                            api_token=token,
                        )
                    if any(scan_text_fields(text).blocked for text in bundle.values()):
                        raise ValueError(BLOCK_NOTICE)
                    st.session_state["comm_bundle"] = bundle
                    st.session_state["comm_bundle_key"] = fingerprint
                    st.session_state.pop("comm_editor", None)
                    st.session_state.pop("comm_result_fingerprint", None)
                    st.rerun()
                messages = build_messages(
                    format_id=format_id,
                    mode=mode,
                    source_text=combined_source,
                    organization=organization,
                    audience=audience,
                    objective=objective + "\nRequested tone: " + tone,
                    visual_description=visual,
                    communication_rules=rules,
                    albanian_rules=albanian,
                    style_id=style_id,
                    output_language=output_language,
                )
                with st.spinner("Preparing the Albanian draft..."):
                    output = generate_communication(messages, account, token)
                if scan_text_fields(output).blocked:
                    st.session_state.pop("comm_editor", None)
                    st.session_state.pop("comm_result_fingerprint", None)
                    st.error(BLOCK_NOTICE)
                    st.stop()
                st.session_state["comm_editor"] = output
                st.session_state["comm_result_fingerprint"] = fingerprint
            except ValueError as exc:
                st.error(friendly_error(exc, context="communication"))


# Four-platform outputs share one source and remain editable in this session.
if (group == "Social Media" and st.session_state.get("comm_bundle_key") == fingerprint
        and st.session_state.get("comm_bundle") and safe):
    bundle = st.session_state["comm_bundle"]
    if any(scan_text_fields(text).blocked for text in bundle.values()):
        st.session_state.pop("comm_bundle", None)
        st.session_state.pop("comm_bundle_key", None)
        st.error(BLOCK_NOTICE)
        st.stop()
    st.divider()
    st.subheader("Social-media campaign drafts")
    st.caption("One source, four platform-specific posts. Review all facts before publication.")
    tabs = st.tabs(["Instagram", "LinkedIn", "Facebook", "X"])
    combined = []
    for panel, platform, label in zip(
        tabs, ("instagram", "linkedin", "facebook", "x"),
        ("Instagram", "LinkedIn", "Facebook", "X")
    ):
        with panel:
            current = st.text_area(
                "Editable " + label + " draft",
                value=bundle[platform],
                height=220,
                key="comm_bundle_edit_" + platform,
            )
            if scan_text_fields(current).blocked:
                st.error(BLOCK_NOTICE)
                st.stop()
            body = extract_publishable_text(current)
            flags = qa_flags(combined_source, current, platform)
            for flag in flags:
                st.warning(flag)
            combined.append(label + "\n\n" + (body or current))
    st.download_button(
        "Download all four posts (.txt)",
        data=("\n\n-----\n\n".join(combined)).encode("utf-8"),
        file_name="ALBA_Social_Campaign_DRAFT.txt",
        mime="text/plain; charset=utf-8",
    )

if scan_text_fields(st.session_state.get("comm_editor", "")).blocked:
    st.session_state.pop("comm_editor", None)
    st.session_state.pop("comm_result_fingerprint", None)
    st.error(BLOCK_NOTICE)
    st.stop()

if (
    st.session_state.get("comm_result_fingerprint") == fingerprint
    and st.session_state.get("comm_editor")
):
    st.divider()
    st.subheader("Generated draft")
    st.text_area(
        "Editable draft (review before publication)",
        key="comm_editor",
        height=340,
    )
    draft = st.session_state["comm_editor"]
    if scan_text_fields(draft).blocked:
        st.session_state.pop("comm_editor", None)
        st.error(BLOCK_NOTICE)
        st.stop()
    extracted = extract_publishable_text(draft)
    if extracted:
        with st.expander("Preview publishable text"):
            st.markdown(extracted)
    flags = qa_flags(combined_source, draft, format_id)
    if flags:
        st.warning("Editorial checks to review:")
        for flag in flags:
            st.write("• " + flag)
    else:
        st.info(
            "No issues were flagged by automated checks. This does not verify facts, "
            "terminology or approval for publication."
        )
    if format_id == "x" and extracted:
        st.caption(
            f"X post length: {len(extracted)} / 280 characters (URL weighting may differ)."
        )

    download_text = extracted if extracted else draft
    st.download_button(
        "Download draft text (.txt)",
        data=download_text,
        file_name="ALBA_Communication_Studio_DRAFT.txt",
        mime="text/plain; charset=utf-8",
    )

    def prepare_adaptation():
        publishable = extract_publishable_text(st.session_state["comm_editor"])
        proposed = publishable or st.session_state["comm_editor"]
        if scan_text_fields(proposed).blocked:
            st.session_state["comm_editor"] = ""
            st.session_state["comm_result_fingerprint"] = ""
            return
        st.session_state["comm_source"] = proposed
        st.session_state["comm_mode"] = "adapt"
        st.session_state["comm_editor"] = ""
        st.session_state["comm_result_fingerprint"] = ""

    st.button(
        "Use this draft for another platform",
        on_click=prepare_adaptation,
        help="Reuse this draft as source material and choose another format.",
    )
elif st.session_state.get("comm_editor"):
    st.info(
        "You changed the format or source material. Click Generate content for a new draft."
    )
