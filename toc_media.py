"""Preserve supported source pictures inside the corresponding Word ToC row.

Pictures are copied from the public source without AI generation, retouching,
OCR, or cropping. Their ORIGINAL binary image bytes and aspect ratio are kept.
For PDF sources image placement is only page-level approximate; vector drawings,
charts and diagrams without extractable raster images cannot be transferred
as original Word graphics. All such limitations must be shown to the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from docx import Document
from docx.oxml.ns import qn

from toc_builder import Provision

MAX_MEDIA_COUNT = 80
MAX_MEDIA_BYTES = 12 * 1024 * 1024
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}


@dataclass(frozen=True)
class SourcePicture:
    offset: int
    data: bytes
    name: str
    width_emu: int | None = None
    height_emu: int | None = None


@dataclass(frozen=True)
class MediaExtraction:
    pictures: tuple[SourcePicture, ...] = ()
    warnings: tuple[str, ...] = ()


def _check_picture(picture: SourcePicture) -> None:
    if not picture.data or len(picture.data) > MAX_MEDIA_BYTES:
        raise ValueError("Source picture cannot be preserved within the size limit.")
    if PurePath(picture.name).suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError(
            "An embedded source picture uses an unsupported image format. "
            "Convert that picture in the original document to PNG or JPEG."
        )


def _word_picture_offsets(paragraph, start: int) -> list[SourcePicture]:
    """Associate each Word image with its text position in its paragraph."""
    pictures = []
    root = paragraph._p
    blips = root.xpath(".//a:blip")
    # Count Word's visible text runs in XML order, retaining intra-paragraph
    # image position; this is more accurate than placing every image at end.
    for blip in blips:
        rid = blip.get(qn("r:embed"))
        if not rid or rid not in paragraph.part.related_parts:
            raise ValueError("The source contains an external or unresolved image.")
        part = paragraph.part.related_parts[rid]
        name = str(part.partname)
        offset = 0
        for node in root.iter():
            if node is blip:
                break
            if node.tag == qn("w:t") and node.text:
                offset += len(node.text)
            elif node.tag == qn("w:tab"):
                offset += 1
            elif node.tag in {qn("w:br"), qn("w:cr")}:
                offset += 1
        extent = next(
            (node for node in blip.iterancestors() if node.tag in {
                qn("wp:inline"), qn("wp:anchor")
            }), None
        )
        size = extent.find(qn("wp:extent")) if extent is not None else None
        width = int(size.get("cx")) if size is not None else None
        height = int(size.get("cy")) if size is not None else None
        pic = SourcePicture(
            offset=start + offset, data=part.blob, name=name,
            width_emu=width, height_emu=height,
        )
        _check_picture(pic)
        pictures.append(pic)
    # Fail visibly for charts, floating shapes and drawings without a
    # transferable embedded raster image rather than claiming to preserve.
    drawings = root.xpath(".//w:drawing")
    if drawings and len(blips) < len(drawings):
        raise ValueError(
            "The Word source contains drawings/charts that cannot be "
            "preserved as embedded pictures. Export them as PNG in the source."
        )
    return pictures


def extract_source_media(filename: str, data: bytes, extracted_text: str) -> MediaExtraction:
    """Read only local source bytes; no external services or image generation."""
    pictures: list[SourcePicture] = []
    warnings: list[str] = []
    if filename.lower().endswith(".docx"):
        doc = Document(BytesIO(data))
        parts = []
        cursor = 0
        for block in doc.iter_inner_content():
            if hasattr(block, "rows"):
                content = "\n".join(
                    "\t".join(cell.text for cell in row.cells)
                    for row in block.rows
                )
                # Table text is flattened by the upstream extractor, so the
                # placement of any image inside a table is only approximate.
                lines = []
                for row in block.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            lines.extend(_word_picture_offsets(p, cursor + len(content)))
                if lines:
                    warnings.append(
                        "Images in source tables are placed after their table text."
                    )
                    pictures.extend(lines)
            else:
                content = block.text
                pictures.extend(_word_picture_offsets(block, cursor))
            parts.append(content)
            cursor += len(content) + 1
        if "\n".join(parts) != extracted_text:
            raise ValueError("Cannot accurately locate pictures in the Word source.")
    elif filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data), strict=False)
        cursor = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            try:
                images = list(page.images)
            except Exception as exc:
                raise ValueError(
                    "The PDF contains images that could not be read for Word export."
                ) from exc
            for image in images:
                # Extracted raster data remains unmodified. Original PDF
                # coordinates are not equivalent to DOCX text cell placement.
                pic = SourcePicture(
                    offset=cursor + max(0, len(text) - 1),
                    data=image.data, name=image.name,
                )
                _check_picture(pic)
                pictures.append(pic)
            cursor += len(text) + 2
        if pictures:
            warnings.append(
                "PDF pictures keep their pixels but are placed approximately "
                "at the end of the associated page's provision. PDF layout "
                "and vector drawings are not reproduced exactly."
            )
    if len(pictures) > MAX_MEDIA_COUNT or sum(len(x.data) for x in pictures) > MAX_MEDIA_BYTES:
        raise ValueError("Too many or too-large source pictures to preserve safely.")
    return MediaExtraction(tuple(pictures), tuple(dict.fromkeys(warnings)))


def group_pictures_by_unit(
    text: str, units: list[Provision], media: MediaExtraction
) -> tuple[dict[str, list[tuple[int, SourcePicture]]], int]:
    """Map original picture offsets to selected units, preserving binary bytes.

    Return a count of pictures outside the selected article range so the UI
    can disclose exclusions instead of silently dropping illustrations.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    mapped: dict[str, list[tuple[int, SourcePicture]]] = {
        unit.reference: [] for unit in units
    }
    bounds = []
    cursor = 0
    for unit in units:
        start = normalized.find(unit.text, cursor)
        if start < 0:
            raise ValueError("Source text and ToC units are no longer aligned.")
        end = start + len(unit.text)
        bounds.append((unit.reference, start, end))
        cursor = end
    omitted = 0
    for pic in media.pictures:
        # A picture exactly at the end of a paragraph belongs to that unit.
        matching = next(
            ((ref, start, end) for ref, start, end in bounds
             if start <= pic.offset <= end),
            None,
        )
        if matching is None:
            omitted += 1
            continue
        ref, start, end = matching
        local = min(max(pic.offset - start, 0), end - start)
        mapped[ref].append((local, pic))
    return mapped, omitted
