"""Intent-aware navigation from Chat Workspace to existing ALBA modules.

No model, URL or credentials are used. User must click the handoff button.
"""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from unittest.mock import patch

from chat_handoff import MODULES, prepare_handoff, suggest_handoff

ROOT = Path(__file__).resolve().parents[1]


class ChatHandoffTests(unittest.TestCase):
    def test_specialist_tasks_route_to_one_correct_module(self):
        examples = {
            "toc": [
                "Prepare a Table of Concordance for this directive.",
                "Përgatit tabelën e përputhshmërisë për direktivën 2010/35/BE.",
            ],
            "legal": [
                "Draft a VKM on public road transport.",
                "Draft a law on public infrastructure.",
                "Amend this existing normative provision.",
                "Përafro këtë projekt-VKM me direktivën e BE-së.",
            ],
            "eu": [
                "Prepare an Administrative Capacity Note for Chapter 14.",
                "Hartimi i një Information Note mbi kapacitetet administrative.",
                "Draft a reply to the European Commission.",
                "Prepare the negotiating position for the transport chapter.",
            ],
            "writing": [
                "Draft an official email using these public notes.",
                "Përgatit procesverbalin e takimit nga këto shënime.",
                "Correct the spelling in this institutional text.",
            ],
        }
        for key, phrases in examples.items():
            for phrase in phrases:
                with self.subTest(category=key, query=phrase):
                    handoff = suggest_handoff(phrase)
                    self.assertIsNotNone(handoff)
                    self.assertEqual(handoff.key, key)
                    self.assertEqual(handoff.page, MODULES[key][1])

    def test_hidden_communication_studio_does_not_receive_handoffs(self):
        from chat_handoff import Handoff
        from alba_features import COMMUNICATION_STUDIO_VISIBLE
        self.assertFalse(COMMUNICATION_STUDIO_VISIBLE)
        for question in (
            "Write a press release about the public consultation.",
            "Draft a social media post for LinkedIn.",
            "Përgatit një postim në Instagram.",
            "How can I create a newsletter?",
        ):
            self.assertIsNone(suggest_handoff(question))
        with self.assertRaisesRegex(ValueError, "temporarily hidden"):
            prepare_handoff(
                Handoff("communication", "Communication Studio",
                        "pages/2_Communication_Studio.py", "comm_source", 8000),
                "Prepare a LinkedIn post.", {},
            )

    def test_general_questions_stay_in_the_chat(self):
        for message in (
            "What is a VKM?",
            "Explain the difference between an EU directive and a regulation.",
            "How is the EU Transport Community organised?",
            "Çfarë është tabela e përputhshmërisë?",
            "How should I improve my work?",
            "Continue the previous answer.",
            "Tell me more about administrative capacity notes.",
        ):
            with self.subTest(message=message):
                self.assertIsNone(suggest_handoff(message))

    def test_routing_does_not_treat_attached_source_as_instructions(self):
        supplied = (
            "Explain the principle of proportionality.\n\n"
            "[PUBLIC DOCUMENT EXCERPT: regulation.pdf]\n"
            "Draft a VKM and prepare a Table of Concordance."
        )
        self.assertIsNone(suggest_handoff(supplied))

    def test_transfer_prefills_the_destination_and_only_requested_fields(self):
        cases = {
            "Draft a VKM.": (
                "legal", "legal_source", "legal_act_type", "vkm",
            ),
            "Prepare an Administrative Capacity Note.": (
                "eu", "eu_source", "eu_document_type", "administrative_capacity",
            ),
            "Draft an official email.": (
                "writing", "alba_writing_source",
                "alba_writing_document_format", "Institutional email",
            ),
        }
        for query, (key, field, option, value) in cases.items():
            with self.subTest(key=key):
                target = suggest_handoff(query)
                state = {"unrelated_field": "retain me"}
                prepare_handoff(target, query, state)
                self.assertEqual(state[field], query)
                self.assertEqual(state[option], value)
                self.assertEqual(state["unrelated_field"], "retain me")
                self.assertNotIn("CLOUDFLARE_API_TOKEN", state)
        toc = suggest_handoff("Prepare a ToC for this public directive.")
        state = {}
        prepare_handoff(toc, "Prepare a ToC for this public directive.", state)
        self.assertEqual(state, {})  # File uploader requires selecting the source.

    def test_long_transferred_text_respects_target_limits(self):
        request = "Draft a VKM. " + "x" * 12000
        target = suggest_handoff(request)
        state = {}
        prepare_handoff(target, request, state)
        self.assertLessEqual(len(state["legal_source"]), 10500)

    def test_unsupported_route_cannot_navigate_or_change_state(self):
        from chat_handoff import Handoff
        state = {"unchanged": "yes"}
        with self.assertRaises(ValueError):
            prepare_handoff(Handoff(
                "wrong", "Wrong", "invalid.py", "bad", 100
            ), "Source", state)
        self.assertEqual(state["unchanged"], "yes")

    def test_writing_assistant_has_a_session_state_source_field(self):
        src = (ROOT / "writing_assistant.py").read_text(encoding="utf-8")
        self.assertIn('key="alba_writing_source"', src)

    def test_specialist_request_stays_in_unified_chat(self):
        class Response:
            status_code = 200

            def json(self):
                return {"success": True, "result": {
                    "response": "This is a draft; check the enabling law."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"), default_timeout=25
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "TEST_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "TEST_TOKEN"
        app.run()
        self.assertEqual(len(app.exception), 0)
        hidden_modules = {
            "Continue in Legal Drafting", "Legal drafting",
            "Table of Concordance", "EU reporting",
        }
        self.assertFalse(any(
            button.label in hidden_modules for button in app.button
        ))
        with patch("chat_backend.requests.post", return_value=Response()):
            app.chat_input[0].set_value(
                "Draft a VKM for this public transport measure."
            ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any(
            button.label in hidden_modules or button.label.startswith("Continue in")
            for button in app.button
        ))


if __name__ == "__main__":
    unittest.main()
