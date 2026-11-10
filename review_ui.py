"""Single opt-in Streamlit control for automatically routed ALBA AI reviews.

The user never has to select an LLM, and no model is contacted merely by
loading or editing a page. Results are independent proposals, not legal advice.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from multi_model_review import (
    PROVIDERS, ReviewOutcome, extract_alternative_wording,
    run_auto_review,
)
from privacy_guard import BLOCK_NOTICE, scan_text_fields


def _get_secret(name: str) -> str:
    try:
        val = st.secrets.get(name, "")
        return val.strip() if isinstance(val, str) else ""
    except Exception:
        return ""


def _google_free_tier_acknowledged() -> bool:
    """Only use Gemini when app owner explicitly confirms free-tier project.

    Google does not expose project billing tier in generation responses;
    this opt-in is an admin assertion, NOT a provider-side hard cost cap.
    """
    try:
        return st.secrets.get("GEMINI_FREE_TIER_CONFIRMED", False) is True
    except Exception:
        return False


def render_auto_review(*, kind: str, source_text: str, draft_text: str,
                       task: str, context_id: str, eu_text: str = "",
                       public_confirmed: bool) -> None:
    """Add one review action with automatic routing and optional alternatives."""
    state = "alba_review_" + context_id
    state_key = state + "_fingerprint"
    st.divider()
    st.subheader("ALBA independent legal and evidence review")
    st.caption(
        "ALBA automatically decides whether one or two checks are justified. "
        "It uses available Google Gemini and/or NVIDIA Nemotron via OpenRouter, "
        "without asking you to choose a model. No revisions are applied automatically."
    )
    st.caption(
        "External free tiers may log prompts and use content to improve models. "
        "Never submit personal, non-public or confidential information. "
        "Gemini is enabled only if the app administrator confirms a free-tier project."
    )
    consent = st.checkbox(
        "I authorize ALBA to send this public/synthetic source and draft to "
        "Google Gemini and/or NVIDIA Nemotron via OpenRouter, as automatically selected.",
        key=state + "_consent",
    )
    if scan_text_fields(source_text, draft_text, eu_text).blocked:
        st.session_state.pop(state, None)
        st.session_state.pop(state_key, None)
        st.error(BLOCK_NOTICE)
        return

    fingerprint = hashlib.sha256(json.dumps({
        "kind": kind, "task": task, "source": source_text,
        "draft": draft_text, "eu": eu_text,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    # Withheld consent or changed material never exposes a prior review.
    if not consent or not public_confirmed:
        st.session_state.pop(state, None)
        st.session_state.pop(state_key, None)

    if st.button("Run ALBA independent review", key=state + "_run"):
        if not consent or not public_confirmed:
            st.warning("The public-material declaration and independent AI consent are required.")
            return
        gemini = _get_secret("GEMINI_API_KEY") if _google_free_tier_acknowledged() else ""
        openrouter = _get_secret("OPENROUTER_API_KEY")
        if not gemini and not openrouter:
            st.warning(
                "No independent free-tier provider is configured. "
                "Add OPENROUTER_API_KEY, or a free-tier GEMINI_API_KEY with "
                "GEMINI_FREE_TIER_CONFIRMED=true in Streamlit secrets."
            )
            return
        try:
            with st.spinner("Checking source fidelity and proposed legal/reporting statements..."):
                result = run_auto_review(
                    kind=kind, source_text=source_text,
                    draft_text=draft_text, eu_text=eu_text, task=task,
                    gemini_key=gemini, openrouter_key=openrouter,
                )
            st.session_state[state] = result
            st.session_state[state_key] = fingerprint
        except ValueError:
            # Avoid exposing provider responses or the submitted text in UI.
            st.error("Independent review was not possible; verify source length and privacy eligibility.")
            return
        except Exception:
            st.error("The independent review service is unavailable.")
            return

    result = st.session_state.get(state)
    if not (
        consent and public_confirmed and isinstance(result, ReviewOutcome)
        and st.session_state.get(state_key) == fingerprint
    ):
        return

    successes = list(result.findings.items())
    if successes:
        st.caption(
            "Completed by: " + ", ".join(PROVIDERS[key] for key, _ in successes) +
            ". Automatic routing: " + result.plan.rationale
        )
        if len(successes) > 1:
            st.info(
                "Two independent assessments are shown separately. "
                "Agreement is not proof; conflicting proposals remain for expert decision."
            )
            panels = st.tabs([PROVIDERS[key] for key, _ in successes])
            for panel, (provider, text) in zip(panels, successes):
                with panel:
                    st.markdown(text)
        else:
            st.markdown(successes[0][1])
        proposals = [
            (provider, extract_alternative_wording(text))
            for provider, text in successes
        ]
        proposals = [(p, text) for p, text in proposals if text]
        if proposals:
            st.subheader("Alternative formulations for expert decision")
            for provider, text in proposals:
                with st.expander("Source-anchored proposals: " + PROVIDERS[provider]):
                    st.markdown(text)
            st.caption(
                "ALBA does not choose or apply these formulations; verify against "
                "the authentic legal or institutional source."
            )
        else:
            st.caption(
                "No source-anchored alternative formulations were proposed."
            )
    for provider, reason in result.errors.items():
        st.warning(PROVIDERS[provider] + ": " + reason)
    if not successes:
        st.warning("No independent assessment could be completed under the current free-tier limits.")
