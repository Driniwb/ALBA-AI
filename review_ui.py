"""ALBA automatic independent review within the existing Cloudflare account.

No Google AI Studio or OpenRouter key, provider chooser, hidden retries,
automatic edits or pay-as-you-go fallback. A single button and source-sharing
confirmation activate independent Cloudflare-hosted model families.
"""
from __future__ import annotations

import hashlib
import json

import streamlit as st

from cloudflare_review import (
    REVIEW_MODELS, CloudflareReviewResult, reviewer_alternatives,
    run_cloudflare_independent_review,
)
from privacy_guard import BLOCK_NOTICE, scan_text_fields


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
        return value.strip() if isinstance(value, str) else ""
    except Exception:
        return ""


def _confirmed_workers_free() -> bool:
    """Must be positively set by administrator; paid accounts may accrue charges."""
    try:
        return st.secrets.get("CLOUDFLARE_FREE_PLAN_CONFIRMED", False) is True
    except Exception:
        return False


def render_auto_review(*, kind: str, source_text: str, draft_text: str,
                       task: str, context_id: str, eu_text: str = "",
                       public_confirmed: bool) -> None:
    state = "alba_review_" + context_id
    state_key = state + "_fingerprint"

    st.divider()
    st.subheader("Independent AI Review")
    st.caption("Optional second check using your Cloudflare models.")
    with st.expander("How this review works"):
        st.write(
            "ALBA chooses reviewers automatically. Uses the free daily "
            "Cloudflare allowance; only enable on a confirmed Workers Free account."
        )

    consent = st.checkbox(
        "I authorize ALBA to submit this public/synthetic source and current "
        "draft to additional Cloudflare-hosted AI models for review.",
        key=state + "_consent",
    )
    if scan_text_fields(source_text, draft_text, eu_text, public_legal=True).blocked:
        st.session_state.pop(state, None)
        st.session_state.pop(state_key, None)
        st.error(BLOCK_NOTICE)
        return

    fingerprint = hashlib.sha256(json.dumps({
        "kind": kind, "task": task, "source": source_text,
        "draft": draft_text, "eu": eu_text,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()

    if not consent or not public_confirmed:
        st.session_state.pop(state, None)
        st.session_state.pop(state_key, None)

    if st.button("Run ALBA independent review", key=state + "_run"):
        if not public_confirmed or not consent:
            st.warning("Confirm public/synthetic material and independent review consent.")
            return
        if not _confirmed_workers_free():
            st.warning(
                "For cost safety, set CLOUDFLARE_FREE_PLAN_CONFIRMED=true in "
                "Streamlit secrets only after checking your account is on Workers Free."
            )
            return
        account, token = (_secret("CLOUDFLARE_ACCOUNT_ID"),
                          _secret("CLOUDFLARE_API_TOKEN"))
        if not account or not token:
            st.warning("Existing Cloudflare Workers AI credentials are missing.")
            return

        try:
            with st.spinner("Reviewing evidence and legal fidelity within Cloudflare..."):
                result = run_cloudflare_independent_review(
                    kind=kind, source_text=source_text, draft_text=draft_text,
                    eu_text=eu_text, task=task, account_id=account,
                    api_token=token,
                )
            st.session_state[state] = result
            st.session_state[state_key] = fingerprint
        except ValueError:
            st.error("Independent review could not run; check source eligibility and length.")
            return
        except Exception:
            st.error("Independent review is unavailable.")
            return

    result = st.session_state.get(state)
    if not (
        consent and public_confirmed and isinstance(result, CloudflareReviewResult)
        and st.session_state.get(state_key) == fingerprint
    ):
        return

    available = list(result.findings.items())
    if available:
        st.caption("Reviewed by " + ", ".join(
            REVIEW_MODELS[k]["name"] for k, _ in available
        ))
        if len(available) > 1:
            tabs = st.tabs([REVIEW_MODELS[k]["name"] for k, _ in available])
            for panel, (_, text) in zip(tabs, available):
                with panel:
                    st.markdown(text)
        else:
            st.markdown(available[0][1])

        alternatives = [
            (key, reviewer_alternatives(text))
            for key, text in available
        ]
        alternatives = [(key, value) for key, value in alternatives if value]
        if alternatives:
            st.subheader("Alternative formulations for expert review")
            for key, value in alternatives:
                with st.expander("Proposed by " + REVIEW_MODELS[key]["name"]):
                    st.markdown(value)
            st.caption("Review proposals before applying them.")

    for key, reason in result.errors.items():
        st.warning(REVIEW_MODELS[key]["name"] + ": " + reason)
    if not available:
        st.warning("No independent review could be completed within current free-tier limits.")
