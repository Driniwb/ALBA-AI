"""Offline acceptance tests for source-grounded Cloudflare independent review.

No actual model calls or personal data. Both critics use the existing Workers
AI account and deterministic automatic model selection.
"""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from cloudflare_review import (
    REVIEW_MODELS, select_cloudflare_review_plan,
    run_cloudflare_independent_review, reviewer_alternatives,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "Neni 4. Transporti i mallrave të rrezikshme kërkon aneksin II."
DRAFT = (
    "### Projektteksti normativ\nNeni 4. Transporti lejohet.\n"
    "### Çështje për verifikim dhe arsyetim\n"
    "Verifikimi mbetet i nevojshëm."
)
REVIEW = (
    "### Independent review findings\n"
    "1. HIGH: The reference to Annex II is missing.\n"
    "### Minimal proposed corrections\n"
    "OLD: Transporti lejohet. NEW: Transporti kërkon aneksin II.\n"
    "### Matters requiring expert verification\n"
    "Verify authentic legal sources; this is not certification."
)
NONE = (
    "### Independent review findings\nNone\n"
    "### Minimal proposed corrections\nNone\n"
    "### Matters requiring expert verification\nConfirm against official sources."
)

class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return {"result": {"response": self.body}}


class CloudflareIndependentReviewTests(unittest.TestCase):
    def test_routing_is_automatic_and_models_have_exact_ids(self):
        self.assertEqual(REVIEW_MODELS["glm"]["id"], "@cf/zai-org/glm-4.7-flash")
        self.assertEqual(REVIEW_MODELS["qwen"]["id"], "@cf/qwen/qwen3.8-27b")
        simple = select_cloudflare_review_plan(
            kind="eu_reporting", task="information_note",
            source_text="A public workshop occurred.",
            draft_text="A public report of the workshop.",
        )
        self.assertEqual(simple.models, ("glm",))
        complex_legal = select_cloudflare_review_plan(
            kind="legal", task="transpose", source_text=SOURCE,
            draft_text=DRAFT, eu_text="Article 3, Annex II",
        )
        self.assertEqual(complex_legal.models, ("glm", "qwen"))
        complex_report = select_cloudflare_review_plan(
            kind="eu_reporting", task="administrative_capacity",
            source_text="4 FTE, 12 inspections, 2 vacancies.",
            draft_text="4 FTE and 12 inspections reported.",
        )
        self.assertEqual(complex_report.models, ("glm", "qwen"))

    def test_two_independent_calls_reuse_same_cloudflare_credentials(self):
        called = []
        def post(url, **kwargs):
            called.append((url, kwargs))
            return FakeResponse(REVIEW if len(called) == 1 else NONE)

        result = run_cloudflare_independent_review(
            kind="legal", source_text=SOURCE, draft_text=DRAFT,
            eu_text="Article 3, Annex II", task="transpose",
            account_id="DEMO_ACCOUNT", api_token="DEMO_TOKEN", post=post,
        )
        self.assertEqual(len(called), 2)
        self.assertEqual(set(result.findings), {"glm", "qwen"})
        self.assertEqual(result.errors, {})
        for i, name in enumerate(("glm", "qwen")):
            url, opts = called[i]
            self.assertTrue(url.endswith(REVIEW_MODELS[name]["id"]))
            self.assertIn("api.cloudflare.com", url)
            self.assertEqual(opts["headers"]["Authorization"], "Bearer DEMO_TOKEN")
            self.assertNotIn("DEMO_TOKEN", str(opts["json"]))
            self.assertEqual(opts["json"]["messages"][0]["role"], "system")

    def test_quota_failure_keeps_one_review_and_never_uses_paid_fallback(self):
        calls = []
        def post(url, **kwargs):
            calls.append(url)
            return FakeResponse(REVIEW if len(calls) == 1 else "", 200 if len(calls) == 1 else 429)
        result = run_cloudflare_independent_review(
            kind="legal", source_text=SOURCE, draft_text=DRAFT,
            task="amend", account_id="DEMO_ACCOUNT",
            api_token="DEMO_TOKEN", post=post,
        )
        self.assertIn("glm", result.findings)
        self.assertIn("qwen", result.errors)
        self.assertEqual(len(calls), 2)

    def test_rejects_private_input_and_invalid_model_response(self):
        with self.assertRaises(ValueError):
            select_cloudflare_review_plan(
                kind="legal", source_text="Contact: example.user@example.org",
                draft_text=DRAFT,
            )
        result = run_cloudflare_independent_review(
            kind="eu_reporting", source_text="A public workshop occurred.",
            draft_text="Workshop report.", task="information_note",
            account_id="DEMO_ACCOUNT", api_token="DEMO_TOKEN",
            post=lambda url, **kwargs: FakeResponse("Incomplete."),
        )
        self.assertFalse(result.findings)
        self.assertIn("glm", result.errors)

    def test_alternatives_only_from_valid_proposals(self):
        self.assertIn("OLD:", reviewer_alternatives(REVIEW))
        self.assertEqual("", reviewer_alternatives(NONE))

    def test_pages_remain_loadable_without_new_secrets(self):
        for name in ("3_Legal_Drafting.py", "4_EU_Reporting.py"):
            path = ROOT / "pages" / name
            app = AppTest.from_file(str(path), default_timeout=25).run()
            self.assertEqual(len(app.exception), 0)
            source = path.read_text(encoding="utf-8")
            self.assertIn("render_auto_review(", source)
            self.assertNotIn("st.selectbox(\"Choose AI model", source)

    def test_ui_uses_cloudflare_only(self):
        ui = (ROOT / "review_ui.py").read_text(encoding="utf-8")
        self.assertIn("run_cloudflare_independent_review(", ui)
        self.assertNotIn("OPENROUTER_API_KEY", ui)
        self.assertNotIn("GEMINI_API_KEY", ui)
        self.assertIn("CLOUDFLARE_FREE_PLAN_CONFIRMED", ui)


if __name__ == "__main__":
    unittest.main()
