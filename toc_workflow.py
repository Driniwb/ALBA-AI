"""Single-upload EU Table of Concordance preparation and seven-column Word export.

All source processing is local. A Cloudflare call is made only by the caller
when the user explicitly requests translation of an English document.
National-law conformity is never inferred, and no source provision is omitted
silently when the document fits the published limits.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import PurePath
import re

from toc_builder import Provision, extract_document, pdf_extraction_flags
from toc_language import detect_toc_language
from toc_media import extract_source_media, group_pictures_by_unit, SourcePicture
from toc_template import built_in_blank_toc, create_toc_using_template
from toc_translation import translated_provisions
from toc_units import split_toc_units
from privacy_guard import BLOCK_NOTICE_SQ, screen_upload, scan_text_fields


@dataclass(frozen=True)
class PreparedToc:
    source_id: str
    filename: str
    title: str
    language: str
    units: tuple[Provision, ...]
    pictures: dict[str, list[tuple[int, SourcePicture]]]
    warnings: tuple[str, ...]


def directive_title(filename: str, text: str) -> str:
    """Identify a source title without inventing a legal act reference."""
    head = text[:12000]
    match = re.search(
        r"(?i)\b(?:DIRECTIVE|DIREKTIV[AEË])\s+"
        r"(?:\((?:EU|BE|EC|KE)\)\s*)?"
        r"\d{4}/\d{1,5}/(?:EU|BE|EC|KE|EEC|KEE)\b",
        head,
    )
    if match:
        return match.group(0).strip()
    # Consolidated CELEX titles have many layouts. Keep the actual source
    # filename instead of inventing the directive's identifier.
    fallback = PurePath(filename).stem.replace("_", " ").strip()
    return fallback[:180] if fallback else "Direktiva e ngarkuar"


def prepare_toc(filename: str, data: bytes) -> PreparedToc:
    """Read and structure the ENTIRE public directive in a single operation."""
    checked = screen_upload(
        filename, data, public_legal=True, max_chars=240000,
    )
    if checked.blocked:
        raise ValueError(BLOCK_NOTICE_SQ)
    extracted = extract_document(filename, data)
    units = split_toc_units(extracted.text)
    if not units or len({u.reference for u in units}) != len(units):
        raise ValueError("Referencat e dispozitave nuk janë identifikuar në mënyrë unike.")
    if not any(re.match(r"^(?:Neni\s+)?\d", u.reference) for u in units):
        raise ValueError("Nenet e direktivës nuk u identifikuan nga dokumenti.")
    if len(units) > 750:
        raise ValueError("Direktiva ka mbi 750 njësi; nuk mund të eksportohet e plotë.")
    language = detect_toc_language(units)
    if language not in {"sq", "en"}:
        raise ValueError(
            "Gjuha e dokumentit nuk u identifikua me siguri. "
            "Përdor një direktivë në shqip ose anglisht."
        )
    media = extract_source_media(filename, data, extracted.text)
    grouped, omitted = group_pictures_by_unit(
        extracted.text, units, media,
    )
    if omitted:
        # A whole-directive export must never pretend to preserve all figures
        # if some were not assigned to a source provision.
        raise ValueError(
            "Disa figura nuk mund të lidhen me dispozitat e dokumentit. "
            "Rishiko formatin e burimit përpara eksportit."
        )
    title = directive_title(filename, extracted.text)
    if scan_text_fields(title, public_legal=True).blocked:
        raise ValueError(BLOCK_NOTICE_SQ)
    warnings = list(extracted.warnings) + list(media.warnings)
    if pdf_extraction_flags(extracted.text):
        warnings.append("PDF-ja mund të përmbajë shënime faqesh ose ndarje fjalësh.")
    if checked.warning:
        warnings.append(checked.warning)
    return PreparedToc(
        source_id=hashlib.sha256(filename.encode("utf-8") + b"\0" + data).hexdigest()[:24],
        filename=filename,
        title=title,
        language=language,
        units=tuple(units),
        pictures=grouped,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def export_word(prepared: PreparedToc, translations: dict[str, str] | None = None) -> bytes:
    """Export the known seven-column Albanian template, no extra UI choices."""
    if prepared.language == "en":
        if translations is None:
            raise ValueError("Përkthimi në shqip nuk është përfunduar.")
        units = translated_provisions(list(prepared.units), translations)
    else:
        units = list(prepared.units)
    return create_toc_using_template(
        built_in_blank_toc(), units, prepared.title,
        media_by_ref=prepared.pictures,
        # English translations change text offsets; PDF extraction positions
        # can also differ. Keep images within their original provision row.
        text_positions_valid=(
            prepared.language == "sq" and prepared.filename.lower().endswith(".docx")
        ),
    )
