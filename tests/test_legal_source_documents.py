"""Deterministic QBZ PDF and version-selection tests; synthetic documents only."""
from datetime import date
from hashlib import sha256
from io import BytesIO
import unittest

from reportlab.pdfgen.canvas import Canvas

from legal_source_documents import (
    _entries, directory_for_eli, retrieve_qbz_document,
)

ELI = "https://qbz.gov.al/eli/vendim/2023/05/31/325"
ROOT = ("https://qbz.gov.al/alfresco/webdav/Aktet/vendim/"
        "keshilli-i-ministrave/2023/05/31/325")
ORIGINAL = "vendim-2023-05-31-325.pdf"
UPDATED = "vendim-2023-05-31-325-i përditësuar.pdf"


def pdf_bytes(*, heading="VENDIM Nr. 325, datë 31.5.2023") -> bytes:
    buffer = BytesIO()
    page = Canvas(buffer)
    page.setFont("Helvetica", 11)
    page.drawString(70, 730, heading)
    page.drawString(70, 710, "PER DISA NDRYSHIME NE STRUKTUREN E PAGAVE TE ADMINISTRATES")
    page.drawString(70, 690, "Neni 1. Ky eshte nje material publik plotesisht sintetik per testim.")
    page.drawString(70, 670, "Neni 2. Ky material nuk eshte nje akt real dhe nuk jep keshilla.")
    page.drawString(70, 650, "VENDOSI: Keto dispozita sherbejne vetem per provat e leximit.")
    page.save()
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, content: bytes, ctype: str, status=200):
        self.content = content
        self.headers = {"Content-Type": ctype}
        self.status_code = status


def directory(links: list[str]) -> FakeResponse:
    html = ("<html><body><h1>Depoja e Permbajtjes</h1>"
            + "".join('<a href="' + link + '">' + link + "</a>" for link in links)
            + "</body></html>")
    return FakeResponse(html.encode("utf-8"), "text/html")


class RecordedGet:
    def __init__(self, *, has_multiple=False, wrong_header=False):
        self.urls = []
        self.base = pdf_bytes()
        self.updated = pdf_bytes(heading=(
            "VENDIM Nr. 999, datë 31.5.2023" if wrong_header else
            "VENDIM Nr. 325, datë 31.5.2023"
        ))
        self.has_multiple = has_multiple

    def __call__(self, url, *, timeout, allow_redirects, headers):
        self.urls.append(url)
        assert allow_redirects is False
        if url == ROOT:
            return directory(["base", "cons-2025-08-05", "cons-2026-07-15",
                              "cons-2027-01-01"])
        if url == ROOT + "/base":
            return directory([ORIGINAL])
        if url in {ROOT + "/cons-2025-08-05", ROOT + "/cons-2026-07-15"}:
            docs = [UPDATED]
            if self.has_multiple:
                docs.append("vendim-2023-05-31-325-tjeter.pdf")
            return directory(docs)
        if url == ROOT + "/base/" + ORIGINAL:
            return FakeResponse(self.base, "application/pdf")
        if "/cons-" in url and url.endswith(".pdf"):
            return FakeResponse(self.updated, "application/pdf")
        raise AssertionError("Unexpected URL: " + url)


class QbzDocumentEvidenceTests(unittest.TestCase):
    def test_only_known_issuer_and_act_type_are_accepted(self):
        self.assertEqual(directory_for_eli(ELI), ROOT)
        with self.assertRaises(ValueError):
            directory_for_eli("https://evil.example/eli/vendim/2023/05/31/325")
        with self.assertRaises(ValueError):
            directory_for_eli("https://qbz.gov.al/eli/udhezim/2023/05/31/325")
        with self.assertRaises(ValueError):
            directory_for_eli("https://qbz.gov.al/eli/vendim/2023/05/31/325-foo")

    def test_select_latest_folder_as_of_and_extract_source_text(self):
        get = RecordedGet()
        evidence, text = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12), get=get,
            expected_sha256=sha256(get.updated).hexdigest(),
        )
        self.assertEqual(evidence.outcome, "document_text_retrieved")
        self.assertEqual(evidence.folder, "cons-2026-07-15")
        self.assertEqual(evidence.folder_cutoff_date, "2026-07-15")
        self.assertTrue(evidence.identity_observed)
        self.assertTrue(evidence.source_text_retrieved)
        self.assertTrue(evidence.expected_sha256_matches)
        self.assertIn("VENDOSI", text)
        self.assertEqual(evidence.page_count, 1)
        self.assertFalse(evidence.version_verified)
        self.assertFalse(evidence.status_verified)
        self.assertFalse(any("2027-01-01" in u for u in get.urls))

    def test_historical_date_uses_earlier_folder(self):
        get = RecordedGet()
        evidence, text = retrieve_qbz_document(
            ELI, as_of=date(2025, 12, 1), get=get,
        )
        self.assertEqual(evidence.folder, "cons-2025-08-05")
        self.assertTrue(len(text) > 100)
        self.assertFalse(evidence.version_verified)

    def test_fallback_base_does_not_become_consolidated_claim(self):
        get = RecordedGet()
        evidence, text = retrieve_qbz_document(
            ELI, as_of=date(2024, 12, 1), get=get,
        )
        self.assertEqual(evidence.folder, "base")
        self.assertIsNone(evidence.folder_cutoff_date)
        self.assertIn("original act", " ".join(evidence.warnings))
        self.assertFalse(evidence.version_verified)

    def test_mismatched_sha_fails_closed(self):
        get = RecordedGet()
        evidence, _ = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12), get=get,
            expected_sha256="0" * 64,
        )
        self.assertEqual(evidence.outcome, "read_or_validation_failed")
        self.assertFalse(evidence.source_text_retrieved)
        self.assertFalse(evidence.version_verified)
        self.assertFalse(evidence.expected_sha256_matches)

    def test_wrong_document_identity_is_not_verified(self):
        evidence, text = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12),
            get=RecordedGet(wrong_header=True),
        )
        self.assertEqual(evidence.outcome, "document_identity_unconfirmed")
        self.assertFalse(evidence.identity_observed)
        self.assertFalse(evidence.version_verified)
        self.assertTrue(len(text) > 100)

    def test_multiple_files_require_explicit_selection(self):
        evidence, _ = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12), get=RecordedGet(has_multiple=True),
        )
        self.assertEqual(evidence.outcome, "read_or_validation_failed")
        self.assertIsNone(evidence.selected_file_url)

    def test_scanned_or_blank_pdf_does_not_count_as_readable_text(self):
        get = RecordedGet()
        blank = BytesIO()
        page = Canvas(blank)
        page.showPage()
        page.save()
        get.updated = blank.getvalue()
        evidence, text = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12), get=get,
        )
        self.assertEqual(evidence.outcome, "read_or_validation_failed")
        self.assertFalse(evidence.source_text_retrieved)
        self.assertFalse(evidence.version_verified)

    def test_empty_portal_shell_is_not_treated_as_a_webdav_index(self):
        get = RecordedGet()
        def nonindex(url, **kwargs):
            if url == ROOT:
                return directory([])
            return get(url, **kwargs)
        evidence, _ = retrieve_qbz_document(
            ELI, as_of=date(2026, 11, 12), get=nonindex,
        )
        self.assertEqual(evidence.outcome, "read_or_validation_failed")
        self.assertIsNone(evidence.selected_file_url)
        self.assertFalse(evidence.status_verified)

    def test_external_links_and_directory_traversal_discarded(self):
        html = """<html><body>
        <a href="https://evil.example/file.pdf">external</a>
        <a href="../../../../admin">traversal</a>
        <a href="cons-2026-07-15">allowed</a>
        <a href="cons-2026-07-15/../../admin">internal traversal</a>
        </body></html>"""
        result = _entries(html, ROOT)
        self.assertEqual(result, [("cons-2026-07-15", ROOT + "/cons-2026-07-15")])


if __name__ == "__main__":
    unittest.main()
