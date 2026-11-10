"""Local-only privacy gate regression tests with entirely synthetic fixtures."""
from io import BytesIO
import unittest

from docx import Document
from pypdf import PdfWriter
from reportlab.pdfgen import canvas

from privacy_guard import (
    BLOCK_NOTICE_SQ,
    combine_safe_text,
    scan_text,
    scan_text_fields,
    screen_upload,
)


def make_docx(*lines: str, header: str = "") -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    if header:
        doc.sections[0].header.paragraphs[0].text = header
    data = BytesIO()
    doc.save(data)
    return data.getvalue()


def make_pdf(*lines: str) -> bytes:
    data = BytesIO()
    c = canvas.Canvas(data)
    for n, line in enumerate(lines):
        c.drawString(40, 770 - 20*n, line)
    c.save()
    return data.getvalue()


class PrivacyGuardTests(unittest.TestCase):
    def test_personal_contact_details_blocked_without_echo(self):
        inputs = [
            "Send response to private.user@example.org",
            "Phone: +355 69 123 4567",
            "Telefon: 0691234567",
            "NID: K12345678Z",
            "Emri: Person Shembull",
            "Datëlindja: 01.01.1990",
            "Llogaria ime bankare: 123456789",
            "Passport number: AB765432",
            "IBAN AL47 2121 1009 0000 0002 3569 8741",
            "Fjalëkalim: sensitivepassword123",
            "Confidential draft institutional note",
            "Medical record: synthetic patient text.",
            "Adresa e banimit: Rruga Shembull 10",
            "-----BEGIN PRIVATE KEY-----",
        ]
        for item in inputs:
            with self.subTest(sample_type=item.split(":")[0][:20]):
                result = scan_text(item)
                self.assertTrue(result.blocked)
                self.assertNotIn("sensitivepassword123", result.notice)
                self.assertNotIn("private.user@", result.notice)
                self.assertEqual(result.notice, BLOCK_NOTICE_SQ)

    def test_safe_public_legal_and_communications_text_passes(self):
        inputs = [
            "Article 1\nMember States shall ensure the transport of goods.",
            "Neni 2\nMinistria njofton konsultimin publik për projektaktin.",
            "Në vitin 2026 zhvillohet një trajnim për transportin urban.",
            "Direktiva 2008/68/KE – transporti i mallrave të rrezikshme",
        ]
        for text in inputs:
            self.assertFalse(scan_text(text).blocked)

    def test_plain_text_upload_allowed_and_combined(self):
        result = screen_upload("brief.txt", b"Activity on public transport in Tirana.")
        self.assertFalse(result.blocked)
        self.assertEqual(
            combine_safe_text("Draft input.", result.text),
            "Draft input.\n\nActivity on public transport in Tirana.",
        )

    def test_sensitive_upload_returns_no_text(self):
        bad = screen_upload("meeting.md", b"Private contact: person.name@example.com")
        self.assertTrue(bad.blocked)
        self.assertEqual(bad.text, "")
        self.assertNotIn("example.com", bad.reason)

    def test_docx_body_and_header_preflight(self):
        safe = screen_upload("sample.docx", make_docx(
            "Article 1", "Public synthetic legal material."
        ))
        self.assertFalse(safe.blocked)
        self.assertIn("Public synthetic", safe.text)

        sensitive = screen_upload(
            "sample.docx", make_docx("Public draft", header="Email: user@example.com")
        )
        self.assertTrue(sensitive.blocked)
        self.assertFalse(sensitive.text)

    def test_scannable_pdf_and_unscannable_pdf(self):
        clean = screen_upload("public.pdf", make_pdf(
            "Article 1", "Public regulations apply."
        ))
        self.assertFalse(clean.blocked)
        self.assertIn("Public regulations", clean.text)

        blank = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        writer.write(blank)
        blocked = screen_upload("scan.pdf", blank.getvalue())
        self.assertTrue(blocked.blocked)

    def test_unsupported_type_and_binary_text_are_blocked(self):
        self.assertTrue(screen_upload("photo.jpg", b"\xff\xd8\xff").blocked)
        self.assertTrue(screen_upload("hidden.txt", b"hello\x00world").blocked)
        self.assertTrue(screen_upload("wrong.pdf", b"not pdf").blocked)
        self.assertTrue(screen_upload("evidence.txt", b"").blocked)

    def test_combined_text_fail_closed_before_model(self):
        with self.assertRaisesRegex(ValueError, "ALBA e bllokoi"):
            combine_safe_text("Public material", "Email: person@example.com")
        with self.assertRaisesRegex(ValueError, "shumë i gjatë"):
            combine_safe_text("a"*300, max_chars=200)

    def test_model_backends_reject_sensitive_text_before_http(self):
        from communication_studio import (
            build_messages, generate_communication, load_library,
        )
        from toc_builder import Provision
        from toc_translation import translate_unit
        sources, rules, albanian = load_library()
        network_calls = []

        def forbidden_post(*args, **kwargs):
            network_calls.append(True)
            raise AssertionError("Network must not be used for sensitive text")

        with self.assertRaisesRegex(ValueError, "ALBA e bllokoi"):
            build_messages(
                format_id="linkedin",
                mode="create",
                source_text="Email: person@example.com",
                organization="Organizata",
                audience="Public",
                objective="Informim",
                visual_description="",
                communication_rules=rules,
                albanian_rules=albanian,
            )
        with self.assertRaisesRegex(ValueError, "ALBA e bllokoi"):
            translate_unit(
                Provision("1.1", "Telefon: +355 69 123 4567"),
                "FAKE_ACCOUNT", "FAKE_TOKEN", post=forbidden_post,
            )
        self.assertEqual(network_calls, [])

    def test_communication_model_output_is_screened_before_display(self):
        from communication_studio import (
            build_messages, generate_communication, load_library,
        )
        sources, rules, albanian = load_library()
        request = build_messages(
            format_id="facebook",
            mode="create",
            source_text="An event about public transport will take place.",
            organization="", audience="", objective="", visual_description="",
            communication_rules=rules,
            albanian_rules=albanian,
        )
        class SensitiveResponse:
            status_code = 200

            def json(self):
                return {
                    "success": True,
                    "result": {"response": (
                        "### Materiali për publikim\\n"
                        "Kontakt privat: private.person@example.org"
                    )},
                }
        with self.assertRaisesRegex(ValueError, "ALBA e bllokoi"):
            generate_communication(
                request, "FAKE_ACCOUNT", "FAKE_TOKEN",
                post=lambda *args, **kwargs: SensitiveResponse(),
            )

    def test_results_have_no_match_or_offsets(self):
        result = scan_text_fields(
            "Public text", "Telephone: +355 69 123 4567"
        )
        self.assertTrue(result.blocked)
        self.assertNotIn("123", str(result))
        self.assertNotIn("+355", str(result))


if __name__ == "__main__":
    unittest.main()
