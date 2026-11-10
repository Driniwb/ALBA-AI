"""Offline tests of literal translation boundary and built-in Word template."""
import ast
from io import BytesIO
import unittest
from pathlib import Path

from docx import Document

from toc_builder import Provision
from toc_template import (
    built_in_blank_toc,
    create_toc_using_template,
    validate_blank_template,
)
from toc_translation import (
    extract_translation,
    translate_unit,
    translated_provisions,
    translation_warnings,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    status_code = 200

    def json(self):
        return {"success": True, "result": {"response": (
            "Neni 1\n1. Shtetet Anëtare mund të marrin masa sipas nenit 2."
        )}}


class TranslationChecks(unittest.TestCase):
    def test_synthetic_builtin_template_is_valid(self):
        source = built_in_blank_toc()
        validate_blank_template(source)
        doc = Document(BytesIO(source))
        self.assertEqual(len(doc.tables[0].columns), 7)
        self.assertIn(
            "Shkalla e përputhshmërisë: [për vlerësim juridik]",
            doc.tables[0].rows[0].cells[2].text,
        )
        out = create_toc_using_template(
            source,
            [Provision("1.1", "Neni 1\n1. Shtetet Anëtare mund të marrin masa.")],
            "Direktiva TEST",
        )
        result = Document(BytesIO(out)).tables[0]
        self.assertEqual(result.rows[3].cells[0].text, "1.1")
        self.assertEqual(
            result.rows[3].cells[1].text,
            "Neni 1\n1. Shtetet Anëtare mund të marrin masa.",
        )
        self.assertTrue(all(
            result.rows[3].cells[c].text == "" for c in range(2, 7)
        ))

    def test_translator_only_sends_selected_source_to_endpoint(self):
        payloads = []
        def fake_post(url, **kwargs):
            payloads.append((url, kwargs))
            return FakeResponse()

        unit = Provision(
            "1.1",
            "Article 1\n1. Member States may take measures under Article 2."
        )
        text, warnings = translate_unit(
            unit, "FAKE_ACCOUNT", "FAKE_TOKEN", post=fake_post
        )
        self.assertTrue(text.startswith("Neni 1"))
        self.assertEqual(warnings, [])
        self.assertEqual(len(payloads), 1)
        self.assertIn("@cf/google/gemma-4-26b-a4b-it", payloads[0][0])
        self.assertEqual(
            payloads[0][1]["headers"]["Authorization"],
            "Bearer FAKE_TOKEN"
        )
        self.assertIn(unit.text, payloads[0][1]["json"]["messages"][1]["content"])
        self.assertFalse(payloads[0][1]["json"]["chat_template_kwargs"]["enable_thinking"])

    def test_flags_numeric_mismatch_and_missing_acronym(self):
        issues = translation_warnings(
            "Article 3: ADR 2008/68/EC (2).",
            "Neni 4: 2008/68/KE (3).",
        )
        self.assertTrue(any("Numra/referenca" in flag for flag in issues))
        self.assertTrue(any("ADR" in flag for flag in issues))

    def test_complete_translations_required_and_references_unchanged(self):
        units = [Provision("1.1", "A"), Provision("1.2", "B")]
        with self.assertRaisesRegex(ValueError, "Mungon përkthimi"):
            translated_provisions(units, {"1.1": "AA"})
        done = translated_provisions(units, {"1.1": "AA", "1.2": "BB"})
        self.assertEqual([p.reference for p in done], ["1.1", "1.2"])
        self.assertEqual([p.text for p in done], ["AA", "BB"])

    def test_empty_and_truncated_responses_are_not_accepted(self):
        with self.assertRaises(ValueError):
            extract_translation({"success": True, "result": {}})
        with self.assertRaisesRegex(ValueError, "ndërpre"):
            extract_translation({
                "result": {"choices": [{
                    "finish_reason": "length",
                    "message": {"content": "Përkthim i paplotë"}
                }]}
            })

    def test_page_is_python_valid_and_in_autodiscovered_pages_dir(self):
        page = ROOT / "pages" / "1_ToC_Builder.py"
        self.assertTrue(page.is_file())
        ast.parse(page.read_text(encoding="utf-8"))
        self.assertIn("Përkthim literal në shqip", page.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
