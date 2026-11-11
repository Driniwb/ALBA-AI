"""ToC page starts without importing deployment-specific article limits."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class TocImportTests(unittest.TestCase):
    def test_page_loads_without_any_user_upload(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("ToC Builder" in title.value for title in app.title))
        self.assertEqual(len(app.text_input), 0)
        self.assertEqual(len(app.number_input), 0)

    def test_page_has_no_stale_capacity_constant_import(self):
        source = (ROOT / "pages" / "1_ToC_Builder.py").read_text(encoding="utf-8")
        self.assertNotIn("MAX_SELECTED_ARTICLES", source)
        self.assertNotIn("first_n_articles", source)
        self.assertIn("from toc_workflow import prepare_toc, export_word", source)


if __name__ == "__main__":
    unittest.main()
