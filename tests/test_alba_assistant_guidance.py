"""ALBA digital assistant must guide to its own modules before external how-tos."""
import unittest

from chat_handoff import app_help_answer, suggest_handoff
from chat_backend import generate_chat_reply, prepare_chat_messages


class ProductGuidanceTests(unittest.TestCase):
    def test_toc_means_concordance_not_table_of_contents(self):
        query = "si mund te ndertoj nje tabele ToC automatikisht?"
        reply = app_help_answer(query)
        self.assertIsNotNone(reply)
        self.assertIn("Table of Concordance", reply)
        self.assertIn("ToC Builder", reply)
        self.assertIn("Word (.docx)", reply)
        self.assertNotIn("Google Docs", reply)
        self.assertNotIn("References →", reply)
        self.assertEqual(suggest_handoff(query).key, "toc")

    def test_product_howto_routes_to_all_existing_modules(self):
        pairs = [
            ("Si mund te hartoj nje VKM ne ALBA?", "legal", "Legal Drafting"),
            ("How to prepare an administrative capacity note?", "eu", "EU Communication & Reporting"),
            ("Si mund te pergatis nje postim ne LinkedIn?", "communication", "Communication Studio"),
            ("How can I write an official email?", "writing", "Writing Assistant"),
        ]
        for query, key, label in pairs:
            with self.subTest(query=query):
                self.assertEqual(suggest_handoff(query).key, key)
                answer = app_help_answer(query)
                self.assertIn(label, answer)
                self.assertNotIn("Google Docs", answer)

    def test_ordinary_question_stays_with_chat_model(self):
        self.assertIsNone(app_help_answer(
            "What are the legal effects of Directive 2008/68/EC?"
        ))
        self.assertIsNone(suggest_handoff(
            "What are the legal effects of Directive 2008/68/EC?"
        ))

    def test_howto_answer_does_not_call_external_ai(self):
        def forbidden_post(*args, **kwargs):
            raise AssertionError("A product-how-to must not send an AI request.")
        result = generate_chat_reply(
            mode="general", history=[],
            user_text="si mund te ndertoj nje tabele ToC automatikisht?",
            account_id="SYNTHETIC", api_token="SYNTHETIC",
            post=forbidden_post,
        )
        self.assertIn("ToC Builder", result)

    def test_system_prompt_describes_modules_and_prevents_toc_confusion(self):
        msg = prepare_chat_messages(
            mode="general", history=[],
            user_text="What can ALBA do with a directive?",
        )[0]["content"]
        self.assertIn("TABLE OF CONCORDANCE", msg)
        self.assertIn("NOT Table of Contents", msg)
        self.assertIn("Legal Drafting", msg)
        self.assertIn("Communication Studio", msg)


if __name__ == "__main__":
    unittest.main()
