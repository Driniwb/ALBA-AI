"""Synthetic test for ALBA's seven-column Word ToC template.

The user-supplied completed ToC and blank model are NOT shipped to GitHub.
"""
from io import BytesIO
import unittest
from docx import Document

from toc_builder import Provision, pdf_extraction_flags, normalise_pdf_display
from toc_template import create_toc_using_template, validate_blank_template
from toc_units import split_toc_units, first_n_articles


def synthetic_blank_template():
    doc = Document()
    doc.add_paragraph("Direktiva ....... (Tabelë përputhshmërie)")
    table = doc.add_table(rows=4, cols=7)
    table.autofit = False
    top = table.rows[0]
    top.cells[0].merge(top.cells[1]).text = "Direktiva ......."
    top.cells[2].merge(top.cells[6]).text = (
        "Legjislacioni shqiptar i propozuar (titulli i projektaktit)\n"
        "1.1. .......\nF – Plotësisht e harmonizuar\n"
        "P – Pjesërisht e harmonizuar\nN – Pa Harmonizuar\n"
        "N/A – jo relevante për përafrim\n"
        "Shkalla e përputhshmërisë: F (e plotë)"
    )
    labels = ("Neni", "Teksti", "Referenca", "Neni", "Përmbajtja",
              "Përputhshmëria", "Komente")
    for c, text in zip(table.rows[1].cells, map(str, range(1, 8))):
        c.text = text
    for c, text in zip(table.rows[2].cells, labels):
        c.text = text
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


SYNTHETIC = (
    "Article 1\nPurpose and scope\n"
    "1. First paragraph.\n"
    "2. Second paragraph:\n"
    "(a) First letter.\n"
    "(b) Second letter.\n"
    "Article 2\nDefinitions\n"
    "(1) Defined term one.\n"
    "(2) Defined term two.\n"
    "Article 3\nGeneral provisions\n"
    "The article contains no numbered paragraphs.\n"
)


class TocTemplateTests(unittest.TestCase):
    def test_accepts_seven_column_blank_and_rejects_populated_template(self):
        blank = synthetic_blank_template()
        validate_blank_template(blank)
        doc = Document(BytesIO(blank))
        doc.tables[0].rows[3].cells[2].text = "internal national reference"
        buf = BytesIO()
        doc.save(buf)
        with self.assertRaisesRegex(ValueError, "BOSHQ"):
            validate_blank_template(buf.getvalue())

    def test_rejects_wrong_number_of_columns(self):
        doc = Document()
        doc.add_table(rows=4, cols=4)
        out = BytesIO()
        doc.save(out)
        with self.assertRaisesRegex(ValueError, "shtatë kolona"):
            validate_blank_template(out.getvalue())

    def test_units_preserve_all_text_and_use_hierarchical_references(self):
        result = split_toc_units(SYNTHETIC)
        refs = [r.reference for r in result]
        self.assertEqual(
            refs,
            ["1", "1.2", "1.2.a", "1.2.b",
             "2", "2.2", "Neni 3"],
        )
        self.assertEqual("\n".join(r.text for r in result), SYNTHETIC)
        self.assertEqual(len(first_n_articles(SYNTHETIC, 2)), 6)

    def test_pdf_layout_cleanup_is_explicit_and_auditable(self):
        sample = (
            "1. This must keep its meaning.\n"
            "(a) under the responsi \u00ad\nbility of the institution;\n"
            "▼B\n\n 02008L0068 — EN — 27.06.2019 — 017.001 — 3  "
        )
        flags = pdf_extraction_flags(sample)
        self.assertEqual(len(flags), 2)
        cleaned = normalise_pdf_display(sample)
        self.assertEqual(
            cleaned,
            "1. This must keep its meaning. (a) under the responsibility "
            "of the institution;"
        )
        self.assertEqual(pdf_extraction_flags(cleaned), [])

    def test_populates_only_eu_columns_and_keeps_template_header(self):
        template = synthetic_blank_template()
        units = first_n_articles(SYNTHETIC, 3)
        out = create_toc_using_template(
            template, units, "Direktiva TEST (fiktive)"
        )
        new = Document(BytesIO(out))
        table = new.tables[0]
        self.assertEqual(len(table.columns), 7)
        self.assertEqual(len(table.rows), len(units) + 3)
        self.assertIs(table.rows[0].cells[0]._tc, table.rows[0].cells[1]._tc)
        self.assertIs(table.rows[0].cells[2]._tc, table.rows[0].cells[6]._tc)
        self.assertIn("[për vlerësim juridik]", table.rows[0].cells[2].text)
        self.assertNotIn("Shkalla e përputhshmërisë: F", table.rows[0].cells[2].text)
        self.assertIn("Direktiva TEST", new.paragraphs[0].text)
        for i, item in enumerate(units, 3):
            self.assertEqual(table.rows[i].cells[0].text, item.reference)
            self.assertEqual(table.rows[i].cells[1].text, item.text)
            self.assertTrue(all(
                not table.rows[i].cells[k].text for k in range(2, 7)
            ))


if __name__ == "__main__":
    unittest.main()
