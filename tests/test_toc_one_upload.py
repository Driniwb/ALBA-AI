"""Single-upload ToC Builder: entire source, no manual selectors, seven-column Word."""
from io import BytesIO
from pathlib import Path
import unittest

from docx import Document

from toc_workflow import prepare_toc, export_word, directive_title
from toc_translation import translation_warnings

ROOT = Path(__file__).resolve().parents[1]


def as_docx(text: str) -> bytes:
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


EN = (
    "DIRECTIVE 2010/35/EU\n"
    "The European Parliament and the Council of the European Union "
    "shall ensure the provisions of this Directive are applied.\n"
    "Article 1\nPurpose and scope\n"
    "1. This Directive establishes the requirements for the Member States.\n"
    "2. The competent authority shall ensure implementation.\n"
    "Article 2\nGeneral rules\n"
    "1. The Member States shall designate the competent authority.\n"
    "ANNEX I\nSafety provisions\n"
    "The conditions of this Annex shall apply to all Member States."
)
SQ = (
    "DIREKTIVA 2010/35/BE\n"
    "Shtetet Anëtare marrin masat për zbatimin e dispozitave të kësaj direktive.\n"
    "Neni 1\nFusha e zbatimit\n"
    "1. Kjo direktivë përcakton kërkesat sipas dispozitave të saj.\n"
    "2. Autoriteti kompetent zbaton kërkesat për transportin.\n"
    "Neni 2\nPërkufizimet\n"
    "1. Ky nen përcakton mjetet dhe pajisjet e transportit.\n"
    "ANEKSI I\nRregulla të veçanta\n"
    "Dispozitat e këtij aneksi zbatohen sipas ligjit."
)


class OneUploadTocTests(unittest.TestCase):
    def test_albanian_source_goes_direct_to_word_without_ai(self):
        source = prepare_toc("Direktiva_2010_35.docx", as_docx(SQ))
        self.assertEqual(source.language, "sq")
        self.assertIn("Neni 1", "\n".join(u.text for u in source.units))
        self.assertIn("ANEKSI I", "\n".join(u.text for u in source.units))
        self.assertEqual(len(source.units), 5)
        self.assertEqual(source.units[1].reference, "1")
        self.assertIn("Fusha e zbatimit", source.units[1].text)
        self.assertIn("1. Kjo", source.units[1].text)
        word = Document(BytesIO(export_word(source)))
        self.assertEqual(len(word.tables), 1)
        self.assertEqual(len(word.tables[0].columns), 7)
        self.assertEqual(len(word.tables[0].rows), len(source.units) + 3)
        for row in word.tables[0].rows[3:]:
            self.assertTrue(row.cells[1].text)
            self.assertTrue(all(
                not row.cells[i].text for i in range(2, 7)
            ))

    def test_english_requires_translation_then_exports_all_including_annex(self):
        source = prepare_toc("directive-2010-35.docx", as_docx(EN))
        self.assertEqual(source.language, "en")
        self.assertIn("ANNEX I", "\n".join(u.text for u in source.units))
        self.assertEqual(len(source.units), 5)
        with self.assertRaisesRegex(ValueError, "Përkthimi"):
            export_word(source)
        translations = {
            unit.reference: "Përkthimi në shqip: " + unit.text
            for unit in source.units
        }
        doc = Document(BytesIO(export_word(source, translations)))
        self.assertEqual(len(doc.tables[0].columns), 7)
        self.assertEqual(len(doc.tables[0].rows), len(source.units) + 3)
        for row in doc.tables[0].rows[3:]:
            self.assertTrue(row.cells[1].text.startswith("Përkthimi"))
        self.assertIn("ANNEX I", doc.tables[0].rows[-1].cells[1].text)

    def test_does_not_silently_discard_intro_or_annex(self):
        src = prepare_toc("source.docx", as_docx(EN))
        contents = "\n".join(u.text for u in src.units)
        self.assertEqual(contents, EN)
        self.assertEqual(src.units[0].reference, "Introductory text / recitals")
        self.assertEqual(src.units[-1].reference, "ANNEX I")

    def test_filenames_do_not_create_fake_eu_directive_numbers(self):
        self.assertEqual(
            directive_title("CELEX_public_act.docx", "Article 1\nPurpose"),
            "CELEX public act",
        )
        self.assertEqual(
            directive_title("a.docx", "DIRECTIVE 2010/35/EU\nArticle 1"),
            "DIRECTIVE 2010/35/EU",
        )

    def test_only_one_upload_widget_and_one_click_translation(self):
        code = (ROOT / "pages" / "1_ToC_Builder.py").read_text(encoding="utf-8")
        self.assertEqual(code.count("st.file_uploader("), 1)
        self.assertNotIn("st.number_input(", code)
        self.assertNotIn("st.selectbox(", code)
        self.assertNotIn("st.checkbox(", code)
        self.assertNotIn("st.text_input(", code)
        self.assertIn("Krijo ToC në Word", code)
        self.assertIn("Shkarko ToC në Word", code)
        self.assertIn("st.rerun()", code)


if __name__ == "__main__":
    unittest.main()
