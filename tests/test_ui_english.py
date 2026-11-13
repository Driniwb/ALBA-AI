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
        for color in ("#f4eedb", "#a9c9b4", "#608f82", "#161d1a", "#e3ac57"):
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
        self.assertIn('page_title="ALBA 2.0"', router)
        self.assertIn('title="ALBA"', router)
        self.assertEqual(router.count("st.Page("), 1)
        self.assertNotIn('title="Writing Assistant"', router)
        self.assertNotIn('title="ToC Builder"', router)
        from alba_features import COMMUNICATION_STUDIO_VISIBLE
        self.assertFalse(COMMUNICATION_STUDIO_VISIBLE)
        self.assertNotIn('Explore **ToC Builder**', router)
        writing = (ROOT / "writing_assistant.py").read_text(encoding="utf-8")
        self.assertNotIn('Explore **ToC Builder**', writing)
        self.assertIn('st.title("Writing Assistant")', writing)
        self.assertIn(".alba-hero", _CSS)

    def test_toc_has_one_upload_and_no_manual_format_configuration(self):
        toc = (ROOT / "pages" / "1_ToC_Builder.py").read_text(encoding="utf-8")
        self.assertEqual(toc.count("st.file_uploader("), 1)
        self.assertNotIn("st.text_input(", toc)
        self.assertNotIn("st.number_input(", toc)
        self.assertNotIn("st.selectbox(", toc)
        self.assertNotIn("template = st.file_uploader", toc)

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
