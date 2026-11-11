"""Reproduce Streamlit's mixed-version hot-reload import failure."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class TocStaleImportTests(unittest.TestCase):
    def test_page_starts_when_old_toc_units_lacks_new_capacity_constant(self):
        # Simulate Streamlit's Python module cache retaining the previous
        # toc_units version while a new ToC page script is re-executed.
        prior_module = types.ModuleType("toc_units")
        prior_module.first_n_articles = lambda text, count=3: []
        with patch.dict(sys.modules, {"toc_units": prior_module}):
            app = AppTest.from_file(
                str(ROOT / "pages" / "1_ToC_Builder.py"),
                default_timeout=25,
            ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("ToC Builder" in t.value for t in app.title))
        self.assertEqual(int(app.number_input[0].max), 8)
        self.assertEqual(int(app.number_input[0].value), 8)

    def test_fresh_module_keeps_expanded_120_article_capacity(self):
        import toc_units
        self.assertEqual(toc_units.MAX_SELECTED_ARTICLES, 120)
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(int(app.number_input[0].max), 120)
        self.assertEqual(int(app.number_input[0].value), 20)


if __name__ == "__main__":
    unittest.main()
