"""Word ToC structure, expanded capacity, and source image retention tests.

All acts and figures used here are synthetic. No Cloudflare API is called.
"""
import base64
from io import BytesIO
import unittest

from docx import Document
from docx.shared import Cm

from toc_builder import Provision, extract_document
from toc_media import extract_source_media, group_pictures_by_unit
from toc_template import built_in_blank_toc, create_toc_using_template
from toc_translation import split_translation_chunks
from toc_units import first_n_articles, split_toc_units, MAX_SELECTED_ARTICLES

# 1x1 valid PNG, created specifically for test input.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/XbUAAAAASUVORK5CYII="
)


class TocCapacityAndMediaTests(unittest.TestCase):
    def test_article_heading_and_title_join_first_point(self):
        src = (
            "Article 1\nPurpose and scope\n1. A synthetic obligation.\n"
            "2. A second paragraph:\n(a) First item.\n(b) Second item.\n"
            "Article 2\nDefinitions\n1. A defined term.\n2. Another term.\n"
        )
        units = split_toc_units(src)
        self.assertEqual([u.reference for u in units], [
            "1", "1.2", "1.2.a", "1.2.b", "2", "2.2"
        ])
        self.assertEqual(
            units[0].text,
            "Article 1\nPurpose and scope\n1. A synthetic obligation.",
        )
        self.assertEqual("\n".join(u.text for u in units), src)
        self.assertFalse(any("hyrja" in u.reference for u in units))
        word = create_toc_using_template(
            built_in_blank_toc(), units, "Synthetic directive"
        )
        table = Document(BytesIO(word)).tables[0]
        self.assertEqual(len(table.columns), 7)
        self.assertEqual(table.cell(3, 0).text, "1")
        self.assertIn("Article 1\nPurpose and scope\n1.",
                      table.cell(3, 1).text)
        self.assertEqual(table.cell(4, 0).text, "1.2")
        self.assertTrue(all(
            not table.cell(3, col).text for col in range(2, 7)
        ))

    def test_up_to_120_articles_are_supported(self):
        src = "\n".join(
            f"Article {i}\nSynthetic subject {i}\n1. No legal effect."
            for i in range(1, 121)
        )
        rows = first_n_articles(src, count=MAX_SELECTED_ARTICLES)
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[0].reference, "1")
        self.assertEqual(rows[-1].reference, "120")
        result = create_toc_using_template(
            built_in_blank_toc(), rows, "Synthetic directive 120"
        )
        exported = Document(BytesIO(result))
        self.assertEqual(len(exported.tables[0].rows), 123)

    def test_chunks_preserve_all_original_characters_and_bound_each_request(self):
        source = (
            "Article 10\n" +
            ("1. A synthetic provision without legal effect.\n" * 200)
        )
        parts = split_translation_chunks(source)
        self.assertGreaterEqual(len(parts), 2)
        self.assertEqual("".join(parts), source)
        self.assertTrue(all(0 < len(part) <= 4200 for part in parts))
        self.assertTrue(all(
            part.endswith("\n") for part in parts[:-1]
        ))

    def test_docx_inline_png_is_preserved_in_the_same_word_row(self):
        original = Document()
        original.add_paragraph("Article 1")
        original.add_paragraph("Synthetic graphic article")
        p = original.add_paragraph()
        p.add_run("1. This public synthetic provision includes a figure. ")
        p.add_run().add_picture(BytesIO(PNG), width=Cm(2))
        original.add_paragraph("2. This second provision has no figure.")
        source_file = BytesIO()
        original.save(source_file)
        source = source_file.getvalue()
        extracted = extract_document("source.docx", source)
        units = first_n_articles(extracted.text, 1)
        media = extract_source_media("source.docx", source, extracted.text)
        self.assertEqual(len(media.pictures), 1)
        self.assertEqual(media.pictures[0].data, PNG)
        grouped, omitted = group_pictures_by_unit(
            extracted.text, units, media
        )
        self.assertEqual(omitted, 0)
        self.assertEqual(len(grouped["1"]), 1)
        word = create_toc_using_template(
            built_in_blank_toc(), units, "Synthetic illustrated directive",
            media_by_ref=grouped,
        )
        exported = Document(BytesIO(word))
        target = exported.tables[0].cell(3, 1)
        self.assertIn("Article 1", target.text)
        self.assertEqual(len(target._tc.xpath(".//a:blip")), 1)
        img_parts = [
            part.blob for rel in exported.part.rels.values()
            for part in [rel.target_part]
            if hasattr(part, "blob") and part.content_type == "image/png"
        ]
        self.assertIn(PNG, img_parts)

    def test_template_logo_is_not_deleted_by_title_replacement(self):
        blank = Document(BytesIO(built_in_blank_toc()))
        title_paragraph = blank.paragraphs[0]
        title_paragraph.add_run(" ")
        title_paragraph.add_run().add_picture(BytesIO(PNG), width=Cm(1))
        stream = BytesIO()
        blank.save(stream)
        word = create_toc_using_template(
            stream.getvalue(),
            [Provision("1", "Article 1\n1. Sample.")],
            "Synthetic",
        )
        out = Document(BytesIO(word))
        self.assertEqual(
            len(out.paragraphs[0]._p.xpath(".//a:blip")), 1
        )
        self.assertIn("Synthetic", out.paragraphs[0].text)


if __name__ == "__main__":
    unittest.main()
