"""ALBA 2.0 — read-only QBZ document-retrieval prototype.

Reads actual PDF files from an explicitly mapped QBZ Alfresco WebDAV folder.
A cons-YYYY-MM-DD repository folder is NOT proof of legal effect, current
consolidation, incorporation of amendments, or continued validity.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import re
from typing import Callable
from urllib.parse import unquote, urljoin, urlsplit

from pypdf import PdfReader
import requests

from legal_sources_probe import validate_official_url

QBZ_REPOSITORY = "https://qbz.gov.al/alfresco/webdav/Aktet"
MAPPED_AUTHORITIES = {"ligj": "kuvendi-i-shqiperise", "vendim": "keshilli-i-ministrave"}
MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_HTML_BYTES = 300_000
MAX_PAGES = 600
MAX_TEXT_CHARS = 750_000
FOLDER = re.compile(r"cons-(\d{4})-(\d{2})-(\d{2})$")
DOCUMENT = re.compile(r"^[a-z]+-\d{4}-\d{2}-\d{2}-\d+(?:[-_ a-zA-Z0-9çëÇË]*)?\.pdf$", re.I)


@dataclass(frozen=True)
class QbzDocumentEvidence:
    eli_url: str
    selected_file_url: str | None
    checked_at_utc: str
    as_of_date: str
    folder: str | None
    folder_cutoff_date: str | None
    pdf_sha256: str | None
    expected_sha256_matches: bool | None
    page_count: int | None
    extracted_characters: int
    identity_observed: bool
    source_text_retrieved: bool
    version_verified: bool
    status_verified: bool
    outcome: str
    warnings: list[str]


class _DirectoryLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._href: str | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            if self._href:
                self.links.append(self._href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a":
            self._href = None


def directory_for_eli(eli: str) -> str:
    """Only mapped laws and Council decisions; no arbitrary user URL fetching."""
    validate_official_url(eli, "AL")
    parts = urlsplit(eli).path.rstrip("/").split("/")
    _, _, kind, year, month, day, number = parts
    if kind not in MAPPED_AUTHORITIES or not number.isdecimal():
        raise ValueError("This act type/issuer has no mapped QBZ repository route.")
    return (
        f"{QBZ_REPOSITORY}/{kind}/{MAPPED_AUTHORITIES[kind]}/"
        f"{year}/{month}/{day}/{number}"
    )


def _entries(html: str, listing_url: str) -> list[tuple[str, str]]:
    parser = _DirectoryLinks()
    parser.feed(html)
    prefix = urlsplit(listing_url).path.rstrip("/") + "/"
    records = []
    for href in parser.links:
        target = urlsplit(urljoin(listing_url.rstrip("/") + "/", href))
        if (target.scheme != "https" or target.hostname != "qbz.gov.al"
                or target.username or target.password or target.port not in (None, 443)
                or target.query or target.fragment):
            continue
        decoded = unquote(target.path)
        if not decoded.startswith(prefix):
            continue
        relative = decoded[len(prefix):].rstrip("/")
        if not relative or "/" in relative or relative in {".", ".."}:
            continue
        records.append((relative, target.geturl()))
    return records


def _get_official(url: str, get: Callable, *, max_size: int, kind: str) -> bytes:
    p = urlsplit(url)
    if (p.scheme != "https" or p.hostname != "qbz.gov.al"
            or not p.path.startswith("/alfresco/webdav/Aktet/")
            or p.username or p.password or p.port not in (None, 443)
            or p.query or p.fragment):
        raise ValueError("Nonofficial or invalid source URL.")
    response = get(url, timeout=12, allow_redirects=False,
                   headers={"User-Agent": "ALBA-QBZ-ReadOnlyPilot/0.2"})
    if response.status_code != 200:
        raise ValueError("QBZ returned HTTP " + str(response.status_code))
    content = response.content
    if len(content) > max_size:
        raise ValueError("QBZ response exceeded size limit.")
    if kind == "listing":
        typ = response.headers.get("Content-Type", "").split(";")[0].lower()
        if typ not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("Directory returned unexpected content type.")
        if b"<html" not in content[:1200].lower():
            raise ValueError("Directory listing is not HTML.")
    elif kind == "pdf" and not content.startswith(b"%PDF-"):
        raise ValueError("Downloaded file is not a PDF.")
    return content


def _heading_matches(text: str, eli: str) -> bool:
    parts = urlsplit(eli).path.rstrip("/").split("/")
    kind, year, number = parts[2], parts[3], parts[6]
    label = "LIGJ" if kind == "ligj" else "VENDIM"
    heading = re.sub(r"\s+", " ", text[:2800])
    return bool(
        re.search(rf"\b{label}\b.{{0,90}}\b[Nn]r\.?\s*{re.escape(number)}\b",
                  heading, re.IGNORECASE)
        and year in heading
    )


def _retrieve(
    eli: str, as_of: date, get: Callable, expected_sha256: str | None,
) -> tuple[QbzDocumentEvidence, str]:
    """Return evidence plus extracted text; never claim legal status."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    folder, cutoff, pdf_url, pdf_hash = None, None, None, None
    hash_matches, pages, text, identity = None, None, "", False
    downloaded = False
    outcome = "unavailable"
    warnings = [
        "Repository cons-folder date is not verified as legal-effect date.",
        "Amendments, repeals and pending changes are not yet reconciled.",
    ]
    try:
        root_url = directory_for_eli(eli)
        root_html = _get_official(root_url, get, max_size=MAX_HTML_BYTES, kind="listing")
        links = _entries(root_html.decode("utf-8", "replace"), root_url)
        selections = []
        base = None
        for label, url in links:
            if label == "base":
                base = url
            match = FOLDER.fullmatch(label)
            if match is None:
                continue
            try:
                folder_date = date(*map(int, match.groups()))
            except ValueError:
                continue
            if folder_date <= as_of:
                selections.append((folder_date, label, url))
        if selections:
            dated, folder, current_url = max(selections, key=lambda item: item[0])
            cutoff = dated.isoformat()
        elif base:
            folder, current_url = "base", base
            warnings.append("No earlier cons-folder was identified; reading original act.")
        else:
            raise ValueError("No original or dated consolidation folder was observed.")
        folder_html = _get_official(current_url, get, max_size=MAX_HTML_BYTES, kind="listing")
        docs = [(name, url) for name, url in
                _entries(folder_html.decode("utf-8", "replace"), current_url)
                if DOCUMENT.fullmatch(name)]
        if len(docs) != 1:
            raise ValueError("Expected exactly one unambiguous PDF in the selected folder.")
        pdf_url = docs[0][1]
        raw = _get_official(pdf_url, get, max_size=MAX_PDF_BYTES, kind="pdf")
        downloaded = True
        pdf_hash = sha256(raw).hexdigest()
        if expected_sha256 is not None:
            if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
                raise ValueError("Expected SHA-256 must be 64 hex digits.")
            hash_matches = pdf_hash.lower() == expected_sha256.lower()
            if not hash_matches:
                raise ValueError("Document hash differs from official metadata.")
        reader = PdfReader(BytesIO(raw), strict=False)
        pages = len(reader.pages)
        if not 0 < pages <= MAX_PAGES:
            raise ValueError("PDF page count outside allowed range.")
        chunks = []
        total = 0
        for page in reader.pages:
            part = page.extract_text() or ""
            total += len(part)
            if total > MAX_TEXT_CHARS:
                raise ValueError("PDF extracted text exceeds limit.")
            chunks.append(part)
        text = "\n".join(chunks).strip()
        if len(text) < 100:
            raise ValueError("Text unreadable; scanned PDF or extraction error.")
        identity = _heading_matches(text, eli)
        if not identity:
            outcome = "document_identity_unconfirmed"
            warnings.append("Document heading did not independently confirm the ELI identity.")
        else:
            outcome = "document_text_retrieved"
    except (requests.RequestException, ValueError, OSError, TypeError) as exc:
        outcome = "read_or_validation_failed"
        warnings.append("Retrieval failed (" + type(exc).__name__ + ").")
    except Exception as exc:
        # PDF parsers raise several library-specific exceptions; never turn
        # those into legal verification or leak raw response contents.
        outcome = "read_or_validation_failed"
        warnings.append("PDF interpretation failed (" + type(exc).__name__ + ").")
    evidence = QbzDocumentEvidence(
        eli_url=eli, selected_file_url=pdf_url,
        checked_at_utc=now, as_of_date=as_of.isoformat(),
        folder=folder, folder_cutoff_date=cutoff, pdf_sha256=pdf_hash,
        expected_sha256_matches=hash_matches, page_count=pages,
        extracted_characters=len(text), identity_observed=identity,
        source_text_retrieved=downloaded and len(text) >= 100,
        version_verified=False, status_verified=False,
        outcome=outcome, warnings=warnings,
    )
    return evidence, text


def retrieve_qbz_document(
    eli: str, *, as_of: date | None = None, get: Callable | None = None,
    expected_sha256: str | None = None,
) -> tuple[QbzDocumentEvidence, str]:
    """Read official QBZ PDF into memory; return evidence and source text."""
    return _retrieve(eli, as_of or date.today(), get or requests.get, expected_sha256)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read QBZ PDF without certifying current law.")
    parser.add_argument("eli", help="Canonical QBZ ELI URL")
    parser.add_argument("--as-of", default=date.today().isoformat())
    args = parser.parse_args()
    evidence, _text = retrieve_qbz_document(args.eli, as_of=date.fromisoformat(args.as_of))
    print(json.dumps(asdict(evidence), ensure_ascii=False, indent=2))
