"""RIA Builder: Albanian Annex 2, private-data gate and output QA."""
import unittest
from io import BytesIO
from unittest.mock import patch
from pathlib import Path

from docx import Document
from streamlit.testing.v1 import AppTest

from ria_builder import (
    RIA_SECTIONS, RIA_METADATA, RIA_EXEMPTIONS,
    build_ria_messages, report_docx, generate_ria_section,
)

ROOT = Path(__file__).resolve().parents[1]


class RIABuilderTests(unittest.TestCase):
    def test_ria_sections_follow_annex_two_not_eu_template(self):
        self.assertEqual(len(RIA_SECTIONS), 9)
        self.assertIn("summary", RIA_SECTIONS)
        self.assertIn("impacts", RIA_SECTIONS)
        self.assertIn("consultation", RIA_SECTIONS)
        self.assertEqual(len(RIA_METADATA), 11)
        self.assertEqual(len(RIA_EXEMPTIONS), 7)

    def test_ria_prompt_uses_status_quo_and_no_fiction(self):
        metadata = {
            "title": "Project for synthetic transport rule",
            "ministry": "Synthetic Ministry",
            "origin": "Transpozim i BE-së",
            "eu_act": "Synthetic public directive",
        }
        m = build_ria_messages(
            section="impacts", metadata=metadata,
            evidence="Test source: two synthetic operators currently report quarterly.",
            options="Opsioni 0: status quo. Opsioni 1: new public portal.",
            consultation="No consultations completed.",
        )
        self.assertEqual(m[0]["role"], "system")
        self.assertIn("Shtojc", m[0]["content"])
        self.assertIn("Mos shpik", m[0]["content"])
        self.assertIn("Opsioni 0", m[1]["content"])
        self.assertIn("dhjetëvjeçar", m[1]["content"])
        self.assertIn("<SOURCE>", m[1]["content"])

    def test_reject_missing_source_or_unknown_section(self):
        with self.assertRaises(ValueError):
            build_ria_messages(section="summary", metadata={},
                               evidence="")
        with self.assertRaises(ValueError):
            build_ria_messages(section="unknown", metadata={},
                               evidence="Public synthetic data.")

    def test_word_export_has_albanian_fields_and_two_annexes(self):
        out = report_docx(
            {"title": "Projektakt provë", "ministry": "Ministri provë"},
            {"summary": "Përmbledhje provë.", "problem": "Problemi provë."},
        )
        doc = Document(BytesIO(out))
        text = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("RAPORTI I VLERËSIMIT", text)
        self.assertIn("Shtojca 2/a", text)
        self.assertIn("Shtojca 2/b", text)
        self.assertIn("PËR T'U PLOTËSUAR", text)
        self.assertGreaterEqual(len(doc.tables), 3)
        self.assertEqual(len(doc.tables[1].columns), 11)

    def test_generation_reuses_reviewed_cloudflare_gate(self):
        with patch("ria_builder.generate_communication",
                   return_value="Pjesa 2 – Analiza e ndikimeve") as mocked:
            out = generate_ria_section(
                build_ria_messages(
                    section="impacts", metadata={"title": "Synthetic"},
                    evidence="Public synthetic data only.",
                ),
                "ACCOUNT", "TOKEN",
            )
        self.assertIn("ndikimeve", out)
        self.assertTrue(mocked.call_args.kwargs["public_legal_source"])

    def test_page_renders_without_ai_credentials_or_network(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "6_RIA_Builder.py"),
            default_timeout=25,
        ).run()
        self.assertFalse(app.exception, str(app.exception))
        self.assertTrue(any("Regulatory Impact Assessment" in x.value for x in app.title))
        self.assertTrue(any(b.key == "ria_generate" for b in app.button))
        self.assertTrue(any(box.key == "ria_current_section" for box in app.selectbox))


if __name__ == "__main__":
    unittest.main()
