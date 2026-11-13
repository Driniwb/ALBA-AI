"""User-selected answer styles and jurisdictions alter the next model prompt."""
import unittest

from chat_backend import ANSWER_STYLES, prepare_chat_messages


class ChatPreferenceTests(unittest.TestCase):
    def test_selected_style_and_jurisdiction_modify_system_instruction(self):
        messages = prepare_chat_messages(
            mode="general", history=[],
            user_text="Explain a public legal obligation.",
            answer_style="Legislative Drafting",
            jurisdictions=["European Union", "Albania"],
        )
        self.assertIn("Selected answer style: Legislative Drafting", messages[0]["content"])
        self.assertIn("European Union, Albania", messages[0]["content"])
        self.assertEqual(messages[-1]["content"], "Explain a public legal obligation.")

    def test_all_styles_available(self):
        self.assertEqual(
            set(ANSWER_STYLES),
            {"Lawyer", "Legal Analysis", "Legislative Drafting",
             "EU Reporting", "Plain Language", "Concise", "Academic"},
        )

    def test_invalid_or_excess_jurisdiction_rejected(self):
        with self.assertRaises(ValueError):
            prepare_chat_messages(
                mode="general", history=[], user_text="Review the act.",
                jurisdictions=["Not a real jurisdiction"],
            )
        with self.assertRaises(ValueError):
            prepare_chat_messages(
                mode="general", history=[], user_text="Review the act.",
                answer_style="Invented style",
            )


if __name__ == "__main__":
    unittest.main()
