"""ALBA contextual follow-up prompts and honest document export guidance."""
import unittest
from unittest.mock import patch

from alba_followups import follow_up_questions
from chat_backend import generate_chat_reply


class FollowupsTests(unittest.TestCase):
    def test_directive_uses_number_and_albanian_approximation(self):
        result = follow_up_questions("Can we check Directive (EU) 2019/520?", "")
        self.assertEqual(len(result), 3)
        self.assertIn("2019/520", result[0])
        self.assertIn("Albania", result[0])
        self.assertIn("table of concordance", result[1])

    def test_albanian_reporting_has_fte_and_institutional_questions(self):
        result = follow_up_questions(
            "Më duhet një Information Note për kapacitetet administrative, Kapitulli 14"
        )
        self.assertEqual(len(result), 3)
        self.assertIn("Kapitullin 14", result[0])
        self.assertIn("FTE", result[1])

    def test_uploaded_document_excerpt_does_not_pollute_followups(self):
        result = follow_up_questions(
            "Si ta hartoj këtë raport?\n\n[PUBLIC DOCUMENT EXCERPT: Sample.pdf]\n"
            "untrusted draft content",
        )
        self.assertEqual(len(result), 3)
        self.assertNotIn("untrusted", " ".join(result))

    def test_document_formats_not_invented(self):
        with patch("chat_backend.requests.post", side_effect=AssertionError("No network")):
            reply = generate_chat_reply(
                mode="general", history=[],
                user_text="Can you generate docs? In what format?",
                account_id="TEST", api_token="TEST",
            )
        self.assertIn(".docx", reply)
        self.assertIn(".md", reply)
        self.assertIn("not yet available", reply)


if __name__ == "__main__":
    unittest.main()
