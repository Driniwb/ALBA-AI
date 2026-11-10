"""Offline test suite for the Word-only Table of Concordance prototype."""
import unittest
from io import BytesIO
from docx import Document
from pypdf import PdfWriter

from toc_builder import extract_document, split_provisions, to_word


SYNTHETIC_DIRECTIVE = (
    "TEST DIRECTIVE — SYNTHETIC ONLY\n"
    "Article 1\n"
    "Purpose\n"
    "1. This example has no legal effect.\n"
    "(a) Text must remain unchanged.\n"
    "(b) The text may contain a word 'Article 9' in a sentence.\n"
    "Article 2\n"
    "Definitions\n"
    "1. 'Sample' means an example.\n"
    "ANNEX I\n"
    "Technical sample\n"
)


class WordTocProof(unittest.TestCase):
    def test_split_keeps_every_character_and_reference_order(self):
        text = SYNTHETIC_DIRECTIVE
        rows = split_provisions(text)
        self.assertEqual(
            [r.reference for r in rows],
            ["Introductory text / recitals", "Article 1", "Article 2", "ANNEX I"],
        )
        self.assertEqual("\n".join(r.text for r in rows), text.rstrip("\n"))
        self.assertIn("(a) Text must remain unchanged.", rows[1].text)

    def test_word_source_and_word_output(self):
        source = Document()
        for line in SYNTHETIC_DIRECTIVE.strip().split("\n"):
            source.add_paragraph(line)
        stream = BytesIO()
        source.save(stream)
        extracted = extract_document("directive.docx", stream.getvalue())
        rows = split_provisions(extracted.text)
        self.assertEqual(len(rows), 4)

        exported = to_word(rows, "directive.docx")
        document = Document(BytesIO(exported))
        self.assertEqual(len(document.tables), 1)
        table = document.tables[0]
        self.assertEqual(len(table.rows), 5)
        self.assertEqual(len(table.columns), 4)
        for i, provision in enumerate(rows, start=1):
            self.assertEqual(table.cell(i, 0).text, provision.reference)
            self.assertEqual(table.cell(i, 1).text, provision.text)
            self.assertEqual(table.cell(i, 2).text, "")
            self.assertEqual(table.cell(i, 3).text, "")

    def test_no_heading_is_not_omitted(self):
        text = "Preliminary material\nNo article heading here.\n"
        rows = split_provisions(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].text, text)

    def test_invalid_or_scanned_pdf_is_rejected(self):
        out = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.write(out)
        with self.assertRaisesRegex(ValueError, "No extractable text"):
            extract_document("scanned.pdf", out.getvalue())

    def test_rejects_unsupported_format(self):
        with self.assertRaisesRegex(ValueError, "Only .docx"):
            extract_document("test.xlsx", b"something")

    def test_pdf_with_text_extracts_without_adding_language(self):
        from reportlab.pdfgen import canvas

        buf = BytesIO()
        pdf = canvas.Canvas(buf, pagesize=(595, 842))
        pdf.drawString(55, 780, "Article 1")
        pdf.drawString(55, 760, "Synthetic provision 1.")
        pdf.drawString(55, 730, "Article 2")
        pdf.drawString(55, 710, "Synthetic provision 2.")
        pdf.save()

        extracted = extract_document("public-test.pdf", buf.getvalue())
        rows = split_provisions(extracted.text)
        self.assertEqual([r.reference for r in rows], ["Article 1", "Article 2"])
        self.assertIn("Synthetic provision 1.", rows[0].text)
        self.assertIn("Synthetic provision 2.", rows[1].text)
        self.assertTrue(any("PDF extraction" in item for item in extracted.warnings))


if __name__ == "__main__":
    unittest.main()
