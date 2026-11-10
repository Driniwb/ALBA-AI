"""Local, fail-closed preflight for public/synthetic ALBA inputs.

No external model, logging, cache or analytics calls. A private file *is*
temporarily read in Streamlit server memory to screen it; no detector can
classify unseen bytes. Never print, return or log matched sensitive values.
The regexes are deliberately heuristic: false positives and missed sensitive
information remain possible. This is not a privacy guarantee or DLP product.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath
from zipfile import BadZipFile, ZipFile
import re
import xml.etree.ElementTree as ET

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 18 * 1024 * 1024
MAX_PDF_PAGES = 35
MAX_ATTACHMENT_TEXT = 10000
SUPPORTED = {".txt", ".md", ".docx", ".pdf"}

BLOCK_NOTICE = (
    "ALBA blocked processing because the material may contain personal, "
    "sensitive or confidential information, or cannot be screened reliably. "
    "No request has been sent to the AI model. Remove identifying information "
    "or use a public/synthetic document."
)
BLOCK_NOTICE_SQ = (
    "ALBA e bllokoi përpunimin: materiali mund të përmbajë të dhëna "
    "personale, sensitive ose konfidenciale, ose nuk kontrollohet me "
    "besueshmëri. Nuk është dërguar kërkesë te modeli AI. "
    "Hiqni identifikuesit ose përdorni material publik/sintetik."
)

# Patterns are only for screening. Matches are *never* surfaced to the UI.
EMAIL = re.compile(r"(?<![\w.+-])[\w.+%-]+@(?:[a-zA-Z0-9-]+\.)+[A-Za-z]{2,}(?!\w)")
AL_NID = re.compile(r"(?<![A-Z0-9])[A-Z]\d{8}[A-Z](?![A-Z0-9])")
IBAN = re.compile(r"(?<!\w)[A-Z]{2}\d{2}(?:[ -]?[A-Z0-9]){11,30}(?!\w)")
PERSONAL_PHONE = re.compile(
    r"(?<![\d])(?:\+355|00355)\s*6[789](?:[\s.-]?\d){7}(?!\d)"
    r"|(?<!\d)06[789](?:[\s.-]?\d){7}(?!\d)"
    r"|(?:\b(?:tel(?:ephone)?|telefon|celular|mobile|cel|phone)\s*[:\-]\s*)"
    r"(?:\+?\d[\s.()\-]?){7,16}",
    re.IGNORECASE,
)
LABELED_ID = re.compile(
    r"\b(?:passport(?:\s+number)?|pasaport(?:ë|a)?|national\s+id|"
    r"personal\s+id|ssn|social\s+security\s+number|"
    r"numri\s+personal|numër\s+identifikimi|nid|"
    r"emri\s+dhe\s+mbiemri|full\s+name|"
    r"mbiemri|emri\s*i\s*personit)"
    r"\s*[:=#-]\s*\S{2,}",
    re.IGNORECASE,
)
CREDENTIALS = re.compile(
    r"\b(?:api[_ -]?key|secret[_ -]?key|password|fjalëkalim|"
    r"authorization|bearer\s+token|access[_ -]?token|private[_ -]?key)"
    r"\s*[:=]\s*\S{6,}",
    re.IGNORECASE,
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE,
)
CONFIDENTIAL = re.compile(
    r"\b(?:strictly confidential|confidential|internal only|"
    r"for internal use only|non-public|secret document|"
    r"konfidencial(?:e)?|sekret\s+(?:shtetëror|profesional)|"
    r"vetëm\s+për\s+përdorim\s+të\s+brendshëm|"
    r"dokument\s+i\s+brendshëm)\b",
    re.IGNORECASE,
)
SENSITIVE_HEALTH = re.compile(
    r"\b(?:medical\s+records?|patient\s+record|diagnos(?:is|ed)|"
    r"raport\s+mjekësor|kartelë\s+mjekësore|"
    r"historik\s+shëndetësor|diagnoz(?:ë|a|uar)|"
    r"rezultat(?:et)?\s+e\s+analizave\s+mjekësore)\b",
    re.IGNORECASE,
)
LABELED_ADDRESS = re.compile(
    r"\b(?:home\s+address|residential\s+address|"
    r"adresa\s+e\s+banimit|adresa\s+personale)"
    r"\s*[:#-]\s*\S{3,}",
    re.IGNORECASE,
)
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


@dataclass(frozen=True)
class ScanResult:
    blocked: bool
    reason: str = ""

    @property
    def notice(self) -> str:
        return BLOCK_NOTICE_SQ


@dataclass(frozen=True)
class AttachmentResult:
    blocked: bool
    text: str = ""
    reason: str = ""


def _valid_card(number: str) -> bool:
    digits = re.sub(r"\D", "", number)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def scan_text(text: str) -> ScanResult:
    """Screen without exposing matches, offsets, substrings or raw PII."""
    if not isinstance(text, str):
        return ScanResult(True, "uninspectable_text")
    if not text:
        return ScanResult(False)
    if (
        EMAIL.search(text)
        or AL_NID.search(text.upper())
        or IBAN.search(text.upper())
        or PERSONAL_PHONE.search(text)
        or LABELED_ID.search(text)
        or CREDENTIALS.search(text)
        or PRIVATE_KEY_BLOCK.search(text)
        or CONFIDENTIAL.search(text)
        or SENSITIVE_HEALTH.search(text)
        or LABELED_ADDRESS.search(text)
    ):
        return ScanResult(True, "sensitive_pattern")
    if any(_valid_card(m.group()) for m in CARD_CANDIDATE.finditer(text)):
        return ScanResult(True, "financial_identifier")
    return ScanResult(False)


def scan_text_fields(*fields: str) -> ScanResult:
    for field in fields:
        result = scan_text(field)
        if result.blocked:
            return result
    return ScanResult(False)


def _pdf_has_images(page) -> bool:
    """Reject image-only or mixed image pages: no OCR or visual PII detection."""
    try:
        resources = page.get("/Resources")
        if not resources:
            return False
        xobjs = resources.get_object().get("/XObject")
        if not xobjs:
            return False
        for obj in xobjs.get_object().values():
            ref = obj.get_object()
            if ref.get("/Subtype") == "/Image":
                return True
    except Exception:
        # Unknown/unsupported layout means the file cannot be screened.
        return True
    return False


def _read_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError("encrypted")
    if not reader.pages or len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError("invalid_page_count")
    text_parts = []
    for page in reader.pages:
        if _pdf_has_images(page):
            raise ValueError("images_not_inspectable")
        text = page.extract_text() or ""
        if not text.strip():
            raise ValueError("textless_page")
        text_parts.append(text)
    return "\n\n".join(text_parts)


def _read_docx(data: bytes) -> str:
    with ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        names = {m.filename for m in members}
        if "word/document.xml" not in names or len(members) > 1500:
            raise ValueError("invalid_docx")
        if sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("uncompressed_limit")
        for m in members:
            if (
                m.file_size > MAX_UNCOMPRESSED_BYTES
                or (m.compress_size and m.file_size > 150 * m.compress_size
                    and m.file_size > 100_000)
            ):
                raise ValueError("decompression_risk")
            lower = m.filename.lower()
            if (
                lower.startswith(("word/media/", "word/embeddings/", "word/activex/"))
                or lower.endswith((".bin", ".exe", ".js", ".vbs"))
            ):
                raise ValueError("embedded_media_or_code")
        collected = []
        # Collect visible text *and* notes, headers, hidden tracked revisions,
        # and document-prop strings for screening; never include markup/bytes.
        for path in sorted(names):
            if not path.endswith(".xml"):
                continue
            if not (
                path.startswith(("word/", "docProps/", "customXml/"))
            ):
                continue
            root = ET.fromstring(archive.read(path))
            for item in root.iter():
                tag = item.tag.rsplit("}", 1)[-1]
                if tag in {"t", "delText", "instrText", "creator", "lastModifiedBy",
                           "description", "subject", "title", "keywords"} and item.text:
                    collected.append(item.text)
        result = "\n".join(collected)
        if not result.strip():
            raise ValueError("no_text")
        return result


def screen_upload(filename: str, data: bytes, *, max_chars: int = MAX_ATTACHMENT_TEXT) -> AttachmentResult:
    """Screen supported attachments in memory before any AI request/preview.

    Block unsupported types, unscannable PDFs or DOCXs with embedded images.
    Never return extracted text for blocked documents.
    """
    if not isinstance(filename, str) or not isinstance(data, bytes):
        return AttachmentResult(True, reason="invalid_upload")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        return AttachmentResult(True, reason="file_size")
    extension = PurePath(filename).suffix.lower()
    if extension not in SUPPORTED:
        return AttachmentResult(True, reason="unsupported_extension")
    if scan_text(filename).blocked:
        return AttachmentResult(True, reason="filename")
    try:
        if extension in {".txt", ".md"}:
            if b"\x00" in data:
                raise ValueError("binary")
            text = data.decode("utf-8-sig")
        elif extension == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("invalid_pdf")
            text = _read_pdf(data)
        else:
            if not data.startswith(b"PK"):
                raise ValueError("invalid_docx")
            text = _read_docx(data)
        if len(text) > max_chars:
            return AttachmentResult(True, reason="too_much_text")
        if scan_text(text).blocked:
            return AttachmentResult(True, reason="sensitive_pattern")
        return AttachmentResult(False, text=text)
    except Exception:
        # Parsing failure is a block, never a partial/unscreened success.
        # Error details may contain identifiers and are deliberately hidden.
        return AttachmentResult(True, reason="uninspectable_file")


def combine_safe_text(*parts: str, max_chars: int = MAX_ATTACHMENT_TEXT) -> str:
    """Fail closed if submitted text is unsafe or exceeds the model bound."""
    for p in parts:
        if scan_text(p).blocked:
            raise ValueError(BLOCK_NOTICE_SQ)
    text = "\n\n".join(p.strip() for p in parts if p and p.strip())
    if len(text) > max_chars:
        raise ValueError(
            "Materiali i bashkuar është shumë i gjatë për analizën e sigurt. "
            "Përdorni një fragment më të shkurtër."
        )
    return text
