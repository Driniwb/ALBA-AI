"""Regression checks for genuinely distinct ALBA document/task controls.

These tests cover observable form behaviour, not only source-code strings.
All example texts are synthetic; no Cloudflare calls or private documents.
"""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from communication_studio import build_messages, load_library

ROOT = Path(__file__).resolve().parents[1]


def _choice(items, name):
    return next(control for control in items if control.label == name)


class OptionDeduplicationTests(unittest.TestCase):
    def test_writing_assistant_tasks_are_actions_not_document_types(self):
        app = AppTest.from_file(
            str(ROOT / "writing_assistant.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        formats = _choice(app.selectbox, "Document format")
        tasks = _choice(app.selectbox, "What do you want to do?")
        self.assertIn("Institutional email", formats.options)
        self.assertIn("Meeting minutes", formats.options)
        self.assertIn("General report (non-EU)", formats.options)
        self.assertIn("Legal text (language review)", formats.options)
        self.assertIn("ToC comments (language review)", formats.options)
        self.assertIn("Draft a document from notes", tasks.options)
        self.assertNotIn("Draft an official email", tasks.options)
        self.assertNotIn("Prepare meeting minutes", tasks.options)
        self.assertTrue(any(
            exp.label == "Optional writing preferences" for exp in app.expander
        ))

    def test_writing_draft_is_available_for_email_and_minutes_only_when_valid(self):
        app = AppTest.from_file(
            str(ROOT / "writing_assistant.py"), default_timeout=25
        ).run()
        _choice(app.selectbox, "Document format").set_value(
            "Institutional email"
        ).run()
        _choice(app.selectbox, "What do you want to do?").set_value(
            "Draft a document from notes"
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            _choice(app.selectbox, "What do you want to do?").value,
            "Draft a document from notes",
        )
        _choice(app.selectbox, "Document format").set_value(
            "Meeting minutes"
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn(
            "Draft a document from notes",
            _choice(app.selectbox, "What do you want to do?").options,
        )

    def test_writing_legal_and_toc_use_language_tasks_not_duplicate_drafting(self):
        for fmt in ("Legal text (language review)", "ToC comments (language review)"):
            with self.subTest(fmt=fmt):
                app = AppTest.from_file(
                    str(ROOT / "writing_assistant.py"), default_timeout=25
                ).run()
                _choice(app.selectbox, "Document format").set_value(fmt).run()
                self.assertEqual(len(app.exception), 0)
                self.assertNotIn(
                    "Draft a document from notes",
                    _choice(app.selectbox, "What do you want to do?").options,
                )
                self.assertIn(
                    "Check legal and administrative terminology",
                    _choice(app.selectbox, "What do you want to do?").options,
                )

    def test_eu_reporting_has_two_distinct_actions_and_optional_details(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "4_EU_Reporting.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            list(app.radio[0].options),
            ["Prepare or adapt a document", "Review an existing draft"],
        )
        self.assertTrue(any(
            exp.label == "Optional reporting details" for exp in app.expander
        ))
        self.assertIn(
            "Administrative Capacity Note",
            app.selectbox[0].options,
        )
        self.assertEqual(
            list(app.selectbox[1].options), ["English", "Albanian"],
        )

    def test_create_or_adapt_preserves_adaptation_guidance(self):
        _, communication, albanian = load_library()
        source = (
            "Existing draft: adopted law and two inspectors; "
            "implementation evidence not confirmed."
        )
        for fmt in ("information_note", "administrative_capacity", "eu_letter"):
            with self.subTest(format=fmt):
                prompt = build_messages(
                    format_id=fmt, mode="create", source_text=source,
                    organization="", audience="", objective="",
                    visual_description="", communication_rules=communication,
                    albanian_rules=albanian, output_language="en",
                    public_legal_source=True,
                )
                self.assertIn("HARTIM OSE PËRSHTATJE", prompt[1]["content"])
                self.assertIn("draft", prompt[1]["content"].lower())
                self.assertIn(source, prompt[1]["content"])
                self.assertEqual(prompt[0]["role"], "system")

    def test_eu_report_formats_are_visible_once_in_navigation(self):
        studio = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(studio.exception), 0)
        self.assertEqual(
            list(studio.selectbox[0].options),
            ["Press & Media", "Newsletter & Web", "Social Media"],
        )
        self.assertNotIn(
            "EU Communication & Reporting", studio.selectbox[0].options
        )
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertEqual(app.count('"pages/4_EU_Reporting.py"'), 1)


if __name__ == "__main__":
    unittest.main()
