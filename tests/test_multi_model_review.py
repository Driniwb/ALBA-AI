"""Offline smoke tests for optional Gemini reviewer and deployed import contracts."""
import importlib
import unittest

from multi_model_review import (
    GEMINI_ENDPOINT,
    build_gemini_review_request,
    generate_gemini_review,
    parse_gemini_result,
)


SOURCE = "Neni 4. Transporti lejohet sipas aneksit I dhe aneksit II."
DRAFT = ("### Projektteksti normativ\nNeni 4. Transporti lejohet.\n"
         "### Çështje për verifikim dhe arsyetim\nKontrollo anekset.")


class Response:
    status_code = 200

    def json(self):
        return {
            "candidates": [{
                "finishReason": "STOP",
                "content": {"parts": [{"text": (
                    "### Independent review findings\n"
                    "HIGH: Source annex references are missing.\n"
                    "### Minimal proposed corrections\n"
                    "Retain original annex references.\n"
                    "### Matters requiring expert verification\n"
                    "Check authentic EU and Albanian legal sources."
                )}]},
            }]
        }


class MultiModelReviewTests(unittest.TestCase):
    def test_gemini_request_is_independent_source_bound_and_low_temperature(self):
        request = build_gemini_review_request(
            kind="legal", source_text=SOURCE, draft_text=DRAFT,
            eu_text="Article 3(1) shall not permit prohibited transport.",
        )
        prompt = request["contents"][0]["parts"][0]["text"]
        self.assertIn(SOURCE, prompt)
        self.assertIn(DRAFT, prompt)
        self.assertIn("Article 3(1)", prompt)
        self.assertIn("independent legal and EU reporting reviewer",
                      request["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(request["generationConfig"]["temperature"], 0.1)

    def test_gemini_call_is_explicit_mocked_and_key_not_in_body(self):
        called = []
        def mock_post(url, **kwargs):
            called.append((url, kwargs))
            return Response()
        result = generate_gemini_review(
            kind="legal", source_text=SOURCE, draft_text=DRAFT,
            api_key="synthetic-demo-key", post=mock_post,
        )
        self.assertIn("Independent review findings", result)
        self.assertEqual(len(called), 1)
        self.assertEqual(called[0][0], GEMINI_ENDPOINT)
        self.assertEqual(called[0][1]["headers"]["x-goog-api-key"], "synthetic-demo-key")
        self.assertNotIn("synthetic-demo-key", str(called[0][1]["json"]))

    def test_privacy_and_missing_credentials_fail_closed(self):
        with self.assertRaises(ValueError):
            build_gemini_review_request(
                kind="legal", source_text="Contact: test@example.org", draft_text=DRAFT)
        with self.assertRaises(ValueError):
            generate_gemini_review(kind="legal", source_text=SOURCE,
                                   draft_text=DRAFT, api_key="")

    def test_invalid_incomplete_gemini_outputs_are_blocked(self):
        with self.assertRaises(ValueError):
            parse_gemini_result({"candidates": [{"finishReason": "MAX_TOKENS",
                                                 "content": {"parts": [{"text":"Partial"}]}}]})
        with self.assertRaises(ValueError):
            parse_gemini_result({"candidates": []})

    def test_import_contracts_match_streamlit_pages(self):
        # Catch ImportError when a page imports a function missing from a backend.
        communication = importlib.import_module("communication_studio")
        legal = importlib.import_module("legal_drafting")
        reviewer = importlib.import_module("multi_model_review")
        for symbol in (
            "FORMATS", "SOCIAL_STYLES", "generate_social_bundle", "build_messages",
            "extract_publishable_text", "generate_communication", "load_library",
            "qa_flags",
        ):
            with self.subTest(symbol=symbol):
                self.assertTrue(hasattr(communication, symbol), symbol)
        for symbol in ("ACT_TYPES", "DRAFT_MODES", "build_legal_messages",
                       "generate_legal_draft", "legal_review_flags"):
            self.assertTrue(hasattr(legal, symbol), symbol)
        self.assertTrue(hasattr(reviewer, "generate_gemini_review"))


if __name__ == "__main__":
    unittest.main()
