"""Offline tests for automatic free-tier multi-provider routing and alternatives.

All source material, model outputs and API keys are synthetic. No network.
"""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

from multi_model_review import (
    OPENROUTER_ENDPOINT, OPENROUTER_MODEL, PROVIDERS,
    build_openrouter_review_request, parse_openrouter_result,
    select_review_plan, run_auto_review, extract_alternative_wording,
)

ROOT = Path(__file__).resolve().parents[1]

LEGAL_SOURCE = (
    "Neni 4. Transporti i mallrave të rrezikshme lejohet në kushtet "
    "e aneksit I dhe aneksit II."
)
LEGAL_DRAFT = (
    "### Projektteksti normativ\n"
    "Neni 4. Transporti i mallrave të rrezikshme lejohet.\n"
    "### Çështje për verifikim dhe arsyetim\n"
    "Verifikim juridik i nevojshëm."
)
EU_SOURCE = (
    "Synthetic capacity note: 6 positions, 4 FTE active, 12 inspections "
    "and 2 vacancies. A measure is drafted but not adopted."
)
EU_DRAFT = (
    "### Draft for transmission\n"
    "The synthetic authority has 4 FTE and carried out 12 inspections.\n"
    "### Verification before submission\n"
    "Verify sources."
)
FINDINGS = (
    "### Independent review findings\n"
    "1. HIGH: Source mentions Annex II but the draft omits it.\n"
    "### Minimal proposed corrections\n"
    "OLD: Transporti lejohet. NEW: Transporti lejohet sipas aneksit II.\n"
    "### Matters requiring expert verification\n"
    "Check the authentic legal text."
)
NO_CHANGES = (
    "### Independent review findings\nNo issues detected from the supplied source.\n"
    "### Minimal proposed corrections\nNone\n"
    "### Matters requiring expert verification\nVerify against official registers."
)


class MockGemini:
    status_code = 200
    def json(self):
        return {"candidates": [{"finishReason": "STOP", "content": {
            "parts": [{"text": FINDINGS}]}}]}


class MockOpenRouter:
    status_code = 200
    def json(self):
        return {"choices": [{"finish_reason": "stop",
                             "message": {"content": NO_CHANGES}}]}


class RateLimitedOpenRouter:
    status_code = 429


class AutomaticReviewTests(unittest.TestCase):
    def test_complex_legal_work_automatically_uses_both_without_user_choice(self):
        plan = select_review_plan(
            kind="legal", task="transpose", source_text=LEGAL_SOURCE,
            draft_text=LEGAL_DRAFT, eu_text="Article 3(1), Annex II",
            available={"gemini", "nemotron"},
        )
        self.assertTrue(plan.comprehensive)
        self.assertEqual(plan.providers, ("nemotron", "gemini"))

    def test_simple_tasks_only_use_one_model(self):
        plan = select_review_plan(
            kind="eu_reporting", task="information_note",
            source_text="Public consultation took place in the city.",
            draft_text="### Draft for transmission\nThe consultation took place.",
            available={"nemotron", "gemini"},
        )
        self.assertFalse(plan.comprehensive)
        self.assertEqual(plan.providers, ("gemini",))

    def test_complex_eu_report_routes_to_two_independent_checks(self):
        plan = select_review_plan(
            kind="eu_reporting", task="administrative_capacity",
            source_text=EU_SOURCE, draft_text=EU_DRAFT,
            available={"gemini", "nemotron"},
        )
        self.assertEqual(plan.providers, ("gemini", "nemotron"))

    def test_missing_key_never_invents_second_provider(self):
        plan = select_review_plan(
            kind="legal", task="transpose", source_text=LEGAL_SOURCE,
            draft_text=LEGAL_DRAFT, available={"gemini"},
        )
        self.assertEqual(plan.providers, ("gemini",))
        with self.assertRaises(ValueError):
            select_review_plan(
                kind="legal", task="transpose", source_text=LEGAL_SOURCE,
                draft_text=LEGAL_DRAFT, available=set(),
            )

    def test_openrouter_request_uses_exact_free_model_not_autorouter(self):
        request = build_openrouter_review_request(
            kind="legal", source_text=LEGAL_SOURCE, draft_text=LEGAL_DRAFT,
        )
        self.assertEqual(OPENROUTER_MODEL, "nvidia/nemotron-3-ultra-550b-a55b:free")
        self.assertEqual(request["model"], OPENROUTER_MODEL)
        self.assertNotEqual(request["model"], "openrouter/free")
        self.assertEqual(request["messages"][0]["role"], "system")

    def test_two_independent_outputs_and_exactly_one_call_each(self):
        calls = {"gemini": 0, "nemotron": 0}
        def google_post(url, **kwargs):
            calls["gemini"] += 1
            self.assertNotIn("SYNTHETIC-KEY", str(kwargs["json"]))
            return MockGemini()
        def router_post(url, **kwargs):
            calls["nemotron"] += 1
            self.assertEqual(url, OPENROUTER_ENDPOINT)
            self.assertEqual(kwargs["json"]["model"], OPENROUTER_MODEL)
            return MockOpenRouter()
        result = run_auto_review(
            kind="legal", task="transpose", source_text=LEGAL_SOURCE,
            draft_text=LEGAL_DRAFT, eu_text="Article 3(1) Annex II",
            gemini_key="SYNTHETIC-KEY", openrouter_key="SYNTHETIC-KEY",
            gemini_post=google_post, openrouter_post=router_post,
        )
        self.assertEqual(calls, {"gemini": 1, "nemotron": 1})
        self.assertEqual(set(result.findings), set(PROVIDERS))
        self.assertEqual(result.errors, {})

    def test_partial_quota_failure_keeps_successful_review_without_paid_fallback(self):
        result = run_auto_review(
            kind="legal", task="transpose", source_text=LEGAL_SOURCE,
            draft_text=LEGAL_DRAFT, gemini_key="FAKE", openrouter_key="FAKE",
            gemini_post=lambda url, **kw: MockGemini(),
            openrouter_post=lambda url, **kw: RateLimitedOpenRouter(),
        )
        self.assertIn("gemini", result.findings)
        self.assertIn("nemotron", result.errors)
        self.assertNotIn("nemotron", result.findings)

    def test_alternatives_present_only_when_grounded_proposals_returned(self):
        self.assertIn("OLD:", extract_alternative_wording(FINDINGS))
        self.assertEqual("", extract_alternative_wording(NO_CHANGES))
        self.assertEqual("", extract_alternative_wording(""))

    def test_incomplete_provider_output_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_openrouter_result({
                "choices": [{"finish_reason": "length",
                             "message": {"content": FINDINGS}}]
            })
        with self.assertRaises(ValueError):
            parse_openrouter_result({
                "choices": [{"finish_reason": "stop",
                             "message": {"content": "Unstructured answer"}}]
            })

    def test_no_model_selector_in_both_pages(self):
        for path in ("3_Legal_Drafting.py", "4_EU_Reporting.py"):
            source = (ROOT / "pages" / path).read_text(encoding="utf-8")
            self.assertIn("render_auto_review(", source)
            self.assertNotIn("st.selectbox(\"Choose AI model", source)
            app = AppTest.from_file(str(ROOT / "pages" / path),
                                    default_timeout=25).run()
            self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
