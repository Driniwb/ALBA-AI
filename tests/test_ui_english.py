"""Regression tests: consistent English UI; Albanian draft output stays intact."""
from pathlib import Path
import unittest

from ui_copy import friendly_error
from privacy_guard import BLOCK_NOTICE, BLOCK_NOTICE_SQ
from communication_studio import FORMATS, SYSTEM_PROMPT as COMMUNICATION_SYSTEM
from toc_translation import SYSTEM_TRANSLATE
from ui_theme import _CSS

ROOT = Path(__file__).resolve().parents[1]


class EnglishInterfaceTests(unittest.TestCase):
    def test_all_three_pages_apply_common_theme(self):
        for path in ("writing_assistant.py", "pages/1_ToC_Builder.py",
                     "pages/2_Communication_Studio.py"):
            with self.subTest(path=path):
                text = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("apply_theme(", text)
        for color in ("#f2fff2", "#add9bc", "#5b8c7c", "#0d1a1a"):
            self.assertIn(color, _CSS)

    def test_internal_rules_are_hidden_not_deleted(self):
        app = (ROOT / "writing_assistant.py").read_text(encoding="utf-8")
        comm = (ROOT / "pages/2_Communication_Studio.py").read_text(encoding="utf-8")
        self.assertNotIn("Reference Library – 3.3", app)
        self.assertNotIn("Other editorial guidance retrieved", app)
        self.assertNotIn("Rregullat aktive për këtë format", comm)
        self.assertIn("communication_rules=rules", comm)

    def test_navigation_uses_alba_brand_and_writing_assistant(self):
        router = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('page_title="ALBA"', router)
        self.assertIn('title="Writing Assistant"', router)
        self.assertIn('title="ToC Builder"', router)
        self.assertIn('title="Communication Studio"', router)
        self.assertNotIn('Explore **ToC Builder**', router)
        writing = (ROOT / "writing_assistant.py").read_text(encoding="utf-8")
        self.assertNotIn('Explore **ToC Builder**', writing)
        self.assertIn('st.title("Writing Assistant")', writing)
        self.assertIn(".alba-hero", _CSS)

    def test_toc_defaults_to_blank_title_and_up_to_eight_articles(self):
        toc = (ROOT / "pages" / "1_ToC_Builder.py").read_text(encoding="utf-8")
        self.assertIn('value=""', toc)
        self.assertIn('list(range(1, 9))', toc)
        self.assertIn('Enter the directive number and title', toc)

    def test_all_format_display_names_are_english(self):
        labels = {item["label"] for item in FORMATS.values()}
        self.assertIn("Press release", labels)
        self.assertIn("Press statement", labels)
        self.assertIn("Website article", labels)
        self.assertIn("Newsletter", labels)
        self.assertTrue(all(not any(c in name for c in ("ë", "ç")) for name in labels))

    def test_english_error_messages_do_not_echo_raw_input(self):
        self.assertEqual(friendly_error(ValueError(BLOCK_NOTICE_SQ)), BLOCK_NOTICE)
        msg = friendly_error(ValueError("Ngarko modelin BOSHQ"), context="template")
        self.assertIn("Word template", msg)
        self.assertNotIn("BOSHQ", msg)
        msg = friendly_error(ValueError("some internal error"), context="toc")
        self.assertIn("directive", msg)
        self.assertNotIn("some internal error", msg)

    def test_albanian_generation_prompts_remain_unchanged_in_intent(self):
        self.assertIn("shqip", COMMUNICATION_SYSTEM)
        self.assertIn("shqip", SYSTEM_TRANSLATE)


if __name__ == "__main__":
    unittest.main()
