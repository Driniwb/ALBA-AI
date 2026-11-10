"""Regression tests: public legislation is not confidential merely by topic.

All documents are synthetic. No private contacts or real official documents.
"""
from io import BytesIO
import unittest

from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from privacy_guard import (
    scan_text, scan_text_fields, screen_upload, combine_safe_text,
    upload_block_message,
)
from legal_drafting import build_legal_messages, generate_legal_draft
from toc_builder import Provision
from toc_translation import translate_unit


LEGAL_TEXT = (
    "LIGJ\nNr. 12/2026\nPËR RUAJTJEN E TË DHËNAVE PERSONALE\n"
    "Neni 1\nKy ligj rregullon konfidencialitetin e të dhënave personale.\n"
    "Neni 2\nTë dhënat e diagnozës përpunohen vetëm sipas ligjit.\n"
    "Neni 3\nMedical records and confidential data must be safeguarded."
)

def docx_bytes(*paras: str) -> bytes:
    doc = Document()
    for line in paras:
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

def pdf_with_logo() -> bytes:
    # A 1x1 PNG is enough to put an /Image object next to extractable text.
    # No photos or real scanned documents are used.
    from PIL import Image
    img = BytesIO()
    Image.new("RGB", (3, 3), (255, 255, 255)).save(img, format="PNG")
    img.seek(0)
    buf = BytesIO()
    pdf = canvas.Canvas(buf)
    pdf.drawImage(ImageReader(img), 35, 730, width=25, height=25)
    pdf.drawString(60, 770, "Official public regulation - Article 1")
    pdf.drawString(60, 755, "The law protects confidential medical records.")
    pdf.save()
    return buf.getvalue()


class MockDraftResponse:
    status_code = 200
    def json(self):
        return {"success": True, "result": {"response": (
            "### Projektteksti normativ\n"
            "Neni 1. Të dhënat konfidenciale mbrohen.\n"
            "### Çështje për verifikim dhe arsyetim\n"
            "Kërkohet verifikim i bazës juridike."
        )}}


class MockTranslateResponse:
    status_code = 200
    def json(self):
        return {"success": True, "result": {"response": (
            "Neni 1. Të dhënat konfidenciale mbrohen sipas këtij ligji."
        )}}


class PublicLegalUploadTests(unittest.TestCase):
    def test_statutory_confidentiality_and_medical_vocabulary_not_private(self):
        self.assertTrue(scan_text(LEGAL_TEXT).blocked)
        self.assertFalse(scan_text(LEGAL_TEXT, public_legal=True).blocked)
        self.assertFalse(scan_text_fields(
            "Neni 4. Personal data shall be processed confidentially.",
            "Neni 5. Medical records are protected.",
            public_legal=True,
        ).blocked)

    def test_actual_classification_and_identifiers_still_blocked(self):
        samples = (
            "KONFIDENCIALE",
            "STRICTLY CONFIDENTIAL",
            "For internal use only",
            "Classification: Confidential",
            "Email: official.person@example.org",
            "NID: K12345678Z",
            "Private key: supersecret123",
            "Datëlindja: 10.10.1990",
            "Medical record: patient details",
        )
        for value in samples:
            with self.subTest(kind=value.split(":")[0]):
                self.assertTrue(scan_text(value, public_legal=True).blocked)

    def test_published_docx_with_legal_vocabulary_passes(self):
        document = docx_bytes(LEGAL_TEXT, "Neni 4: Autoriteti ruan konfidencialitetin.")
        generic = screen_upload("law.docx", document)
        self.assertTrue(generic.blocked)
        legal = screen_upload("law.docx", document, public_legal=True)
        self.assertFalse(legal.blocked)
        self.assertIn("konfidencialitetin", legal.text)
        self.assertIn("Neni 4", legal.text)

    def test_text_based_public_pdf_with_logo_is_accepted_without_image_bytes(self):
        document = pdf_with_logo()
        self.assertTrue(screen_upload("regulation.pdf", document).blocked)
        legal = screen_upload("regulation.pdf", document, public_legal=True)
        self.assertFalse(legal.blocked, legal.reason)
        self.assertIn("Article 1", legal.text)
        self.assertTrue(legal.warning)
        self.assertNotIn("PNG", legal.text)

    def test_long_published_law_can_be_read_before_selecting_an_excerpt(self):
        body = LEGAL_TEXT + "\n" + ("Neni 4. Zbatimi i ligjit. " * 500)
        law = screen_upload(
            "published_law.docx", docx_bytes(body),
            public_legal=True, max_chars=200000,
        )
        self.assertFalse(law.blocked)
        self.assertGreater(len(law.text), 6500)
        selected = law.text[:7500]
        self.assertFalse(
            scan_text(combine_safe_text(selected, public_legal=True),
                      public_legal=True).blocked
        )
        with self.assertRaises(ValueError):
            combine_safe_text(law.text, max_chars=10500, public_legal=True)

    def test_blocked_upload_has_safe_actionable_category(self):
        msg = upload_block_message("uninspectable_file")
        self.assertIn("PDF", msg)
        self.assertNotIn("private.email", msg)
        self.assertTrue(screen_upload(
            "public.docx", docx_bytes(
                "Neni 1. Për kontakt shkruani në private.person@example.org."
            ), public_legal=True,
        ).blocked)

    def test_legal_model_pipeline_accepts_normative_terms_without_disabling_pii(self):
        messages = build_legal_messages(
            act_type="law", mode="review",
            source_text=LEGAL_TEXT, drafting_goal="Rishikim i nenit 2.",
        )
        draft = generate_legal_draft(
            messages, "FAKE_ACCOUNT", "FAKE_TOKEN",
            post=lambda url, **kwargs: MockDraftResponse(),
        )
        self.assertIn("konfidenciale", draft)

        with self.assertRaises(ValueError):
            build_legal_messages(
                act_type="law", mode="review",
                source_text=LEGAL_TEXT + "\nEmail: private@example.org",
            )

    def test_toc_translation_keeps_public_law_vocabulary(self):
        translated, _ = translate_unit(
            Provision(
                "1", "Article 1. Medical records must remain confidential."
            ),
            "FAKE_ACCOUNT", "FAKE_TOKEN",
            post=lambda url, **kwargs: MockTranslateResponse(),
        )
        self.assertIn("konfidenciale", translated)


if __name__ == "__main__":
    unittest.main()
