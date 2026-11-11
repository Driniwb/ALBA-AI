"""Local language detection and automatic ToC export decisions."""
import ast
from pathlib import Path
import unittest

from toc_builder import Provision
from toc_language import detect_toc_language

ROOT = Path(__file__).resolve().parents[1]

class TocLanguageTests(unittest.TestCase):
    def test_english_directive_requires_translation(self):
        units = [
            Provision("Neni 1 (hyrja)",
                      "Article 1\nPurpose and scope\nThe Member States shall "
                      "ensure that the provisions of this Directive apply."),
            Provision("1.1", "1. The competent authority shall take appropriate measures."),
        ]
        self.assertEqual(detect_toc_language(units), "en")

    def test_albanian_directive_is_preserved(self):
        units = [
            Provision("Neni 1 (hyrja)",
                      "Neni 1\nQëllimi dhe fusha e zbatimit\n"
                      "Shtetet Anëtare marrin masat sipas dispozitave të këtij ligji."),
            Provision("1.1", "1. Ky nen zbatohet në transportin e mallrave dhe pajisjeve."),
        ]
        self.assertEqual(detect_toc_language(units), "sq")

    def test_mixed_and_unclear_language_never_guessed(self):
        self.assertEqual(
            detect_toc_language([
                Provision("Neni 1", "Article 1\nThe Member States shall act."),
                Provision("Neni 2", "Neni 2\nShtetet Anëtare zbatojnë dispozitat."),
            ]),
            "uncertain",
        )
        self.assertEqual(detect_toc_language([Provision("1.1", "1. 2008/68/EC ADR")]), "uncertain")
        self.assertEqual(detect_toc_language([]), "uncertain")

    def test_page_does_not_offer_manual_source_language_switch(self):
        page = (ROOT / "pages" / "1_ToC_Builder.py").read_text(encoding="utf-8")
        workflow = (ROOT / "toc_workflow.py").read_text(encoding="utf-8")
        ast.parse(page)
        ast.parse(workflow)
        self.assertNotIn('"Content of column 2"', page)
        self.assertNotIn('"Literal Albanian translation (AI)"', page)
        self.assertNotIn('"Original text (no translation)"', page)
        self.assertIn("detect_toc_language(units)", workflow)
        self.assertIn("prepare_toc(", page)


if __name__ == "__main__":
    unittest.main()
