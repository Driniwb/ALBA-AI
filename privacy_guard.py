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
MAX_PUBLIC_LEGAL_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 18 * 1024 * 1024
MAX_PDF_PAGES = 35
MAX_PUBLIC_LEGAL_PDF_PAGES = 180
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
LABELED_PERSON = re.compile(
    r"(?im)^\s*(?:full\s+name|first\s+and\s+last\s+name|"
    r"name|surname|last\s+name|emri|mbiemri|"
    r"emri\s+dhe\s+mbiemri|datëlindja|date\s+of\s+birth)"
    r"\s*[:=#-]\s*\S{2,}",
    re.IGNORECASE,
)
PERSONAL_FINANCE = re.compile(
    r"\b(?:my\s+(?:salary|bank\s+account)|"
    r"paga\s+ime|llogaria\s+ime\s+bankare|"
    r"account\s+number|bank\s+account\s+number|"
    r"numri\s+i\s+llogarisë\s+bankare)"
    r"\s*[:#-]?\s*[\w\d€$]{3,}",
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
# Public acts discuss confidentiality, health, and privacy as legal concepts.
# Treat such vocabulary as non-sensitive ONLY in the public-law workflow.
# Explicit classification markers and filled patient fields remain forbidden.
CLASSIFICATION_LABEL = re.compile(
    r"(?im)^\s*(?:(?:strictly\s+confidential|for\s+internal\s+use\s+only|"
    r"vetëm\s+për\s+përdorim\s+të\s+brendshëm|"
    r"konfidenciale?\s*(?:[-–]\s*(?:draft|projekt|i\s+brendshëm))?|"
    r"confidential\s+(?:draft|document|report|memo|note))\s*"
    r"|(?:classification|klasifikimi)\s*[:=-]\s*"
    r"(?:confidential|konfidencial|secret|sekret))\s*$",
    re.IGNORECASE,
)
PRIVATE_CASE_LABEL = re.compile(
    r"(?im)^\s*(?:patient\s+(?:record|name)|medical\s+record|"
    r"kartelë\s+mjekësore|diagnoz[ëa]|date\s+of\s+birth|datëlindja)"
    r"\s*[:=]\s*\S+",
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
    warning: str = ""


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


def scan_text(text: str, *, public_legal: bool = False) -> ScanResult:
    """Screen without exposing matches; allow normative vocabulary in public acts.

    Public-law mode is only for declared, published legislation. It relaxes
    *topic words*, not credential, personal-identifier or classification checks.
    """
    if not isinstance(text, str):
        return ScanResult(True, "uninspectable_text")
    if not text:
        return ScanResult(False)
    hard_patterns = (
        EMAIL, AL_NID, IBAN, PERSONAL_PHONE, LABELED_ID,
        LABELED_PERSON, PERSONAL_FINANCE, CREDENTIALS,
        PRIVATE_KEY_BLOCK, LABELED_ADDRESS,
    )
    if (
        any(pattern.search(text.upper() if pattern in (AL_NID, IBAN) else text)
            for pattern in hard_patterns)
        or CLASSIFICATION_LABEL.search(text)
    ):
        return ScanResult(True, "sensitive_pattern")
    if public_legal:
        if PRIVATE_CASE_LABEL.search(text):
            return ScanResult(True, "sensitive_pattern")
    elif CONFIDENTIAL.search(text) or SENSITIVE_HEALTH.search(text):
        return ScanResult(True, "sensitive_pattern")
    if any(_valid_card(m.group()) for m in CARD_CANDIDATE.finditer(text)):
        return ScanResult(True, "financial_identifier")
    return ScanResult(False)


def scan_text_fields(*fields: str, public_legal: bool = False) -> ScanResult:
    for field in fields:
        result = scan_text(field, public_legal=public_legal)
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


def _read_pdf(data: bytes, *, public_legal: bool = False) -> tuple[str, bool]:
    """Extract PDF text only. Graphics never reach the AI model.

    A public legal PDF may contain a logo, stamp or diagram. Its readable
    text is still extractable; clearly warn that images/figures are omitted.
    Image-only, encrypted, textless pages are never accepted.
    """
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=False)
    if reader.is_encrypted:
        raise ValueError("encrypted")
    max_pages = MAX_PUBLIC_LEGAL_PDF_PAGES if public_legal else MAX_PDF_PAGES
    if not reader.pages or len(reader.pages) > max_pages:
        raise ValueError("invalid_page_count")
    text_parts = []
    has_images = False
    for page in reader.pages:
        contains_images = _pdf_has_images(page)
        if contains_images and not public_legal:
            raise ValueError("images_not_inspectable")
        text = page.extract_text() or ""
        if not text.strip():
            raise ValueError("textless_page")
        text_parts.append(text)
        has_images = has_images or contains_images
    return "\n\n".join(text_parts), has_images


def _read_docx(data: bytes, *, public_legal: bool = False) -> tuple[str, bool]:
    with ZipFile(BytesIO(data)) as archive:
        members = archive.infolist()
        names = {m.filename for m in members}
        if "word/document.xml" not in names or len(members) > 1500:
            raise ValueError("invalid_docx")
        if sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("uncompressed_limit")
        contains_media = False
        for m in members:
            if (
                m.file_size > MAX_UNCOMPRESSED_BYTES
                or (m.compress_size and m.file_size > 150 * m.compress_size
                    and m.file_size > 100_000)
            ):
                raise ValueError("decompression_risk")
            lower = m.filename.lower()
            if lower.startswith("word/media/"):
                if not public_legal or not lower.endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".bmp",
                     ".tif", ".tiff", ".emf", ".wmf")
                ):
                    raise ValueError("embedded_media_or_code")
                contains_media = True
            if (
                lower.startswith(("word/embeddings/", "word/activex/"))
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
        return result, contains_media


def screen_upload(
    filename: str,
    data: bytes,
    *,
    max_chars: int = MAX_ATTACHMENT_TEXT,
    public_legal: bool = False,
) -> AttachmentResult:
    """Screen uploaded text, with a dedicated public normative-act workflow.

    Public-law mode requires explicit user declaration in the calling UI.
    Every byte stays in Streamlit's upload processing; only extracted and
    screened TEXT can be submitted to the model, never embedded images.
    """
    if not isinstance(filename, str) or not isinstance(data, bytes):
        return AttachmentResult(True, reason="invalid_upload")
    upload_limit = (
        MAX_PUBLIC_LEGAL_UPLOAD_BYTES if public_legal else MAX_UPLOAD_BYTES
    )
    if not data or len(data) > upload_limit:
        return AttachmentResult(True, reason="file_size")
    extension = PurePath(filename).suffix.lower()
    if extension not in SUPPORTED:
        return AttachmentResult(True, reason="unsupported_extension")
    if scan_text(filename, public_legal=public_legal).blocked:
        return AttachmentResult(True, reason="filename")
    warning = ""
    try:
        if extension in {".txt", ".md"}:
            if b"\x00" in data:
                raise ValueError("binary")
            text = data.decode("utf-8-sig")
        elif extension == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise ValueError("invalid_pdf")
            text, has_images = _read_pdf(data, public_legal=public_legal)
            if has_images:
                warning = (
                    "PDF has images or graphics that ALBA did not read. "
                    "Only extracted text will be used; verify figures and annexes."
                )
        else:
            if not data.startswith(b"PK"):
                raise ValueError("invalid_docx")
            text, has_media = _read_docx(data, public_legal=public_legal)
            if has_media:
                warning = (
                    "DOCX has images that ALBA did not read. "
                    "Only extracted text will be used; verify any diagram or annex."
                )
        if len(text) > max_chars:
            return AttachmentResult(True, reason="too_much_text")
        if scan_text(text, public_legal=public_legal).blocked:
            return AttachmentResult(True, reason="sensitive_pattern")
        return AttachmentResult(False, text=text, warning=warning)
    except Exception:
        return AttachmentResult(True, reason="uninspectable_file")


def combine_safe_text(
    *parts: str, max_chars: int = MAX_ATTACHMENT_TEXT, public_legal: bool = False
) -> str:
    """Join only screened text; prohibit silent truncation."""
    for p in parts:
        if scan_text(p, public_legal=public_legal).blocked:
            raise ValueError(BLOCK_NOTICE_SQ)
    text = "\n\n".join(p.strip() for p in parts if p and p.strip())
    if len(text) > max_chars:
        raise ValueError(
            "Materiali i përzgjedhur është shumë i gjatë për një kërkesë AI. "
            "Zgjidhni nenet ose fragmentin për analizë."
        )
    return text


def upload_block_message(reason: str) -> str:
    """Share a useful category, never a sensitive match or excerpt."""
    guidance = {
        "too_much_text": (
            "Dokumenti është më i gjatë se kufiri i përpunimit. "
            "Përdorni një akt ose fragment më të shkurtër."
        ),
        "file_size": (
            "Dokumenti tejkalon kufirin e ngarkimit (12 MB për akte ligjore) ose është bosh. "
            "Ngarkoni një version më të vogël të aktit publik."
        ),
        "uninspectable_file": (
            "PDF/DOCX nuk mund të lexohet plotësisht: mund të jetë i skanuar, "
            "i enkriptuar, me faqe pa tekst ose me format të pambështetur. "
            "Përdorni PDF me tekst të përzgjedhshëm ose DOCX/TXT."
        ),
        "sensitive_pattern": BLOCK_NOTICE,
        "filename": BLOCK_NOTICE,
    }
    return guidance.get(reason, BLOCK_NOTICE)
