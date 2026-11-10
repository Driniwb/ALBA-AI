"""Fill the user's blank seven-column Albanian ToC template without redesigning it.

The blank DOCX is supplied at runtime, never committed or stored server-side.
Only column 1 (provision reference) and column 2 (extracted EU text) are filled.
No national-law mapping, equivalence or legal assessment is performed.
"""
from copy import deepcopy
from io import BytesIO
import re

from docx import Document

from toc_builder import Provision

MAX_TEMPLATE_BYTES = 4 * 1024 * 1024
EXPECTED = (
    "Neni", "Teksti", "Referenca", "Neni",
    "Përmbajtja", "Përputhshmëria", "Komente",
)


def validate_blank_template(template: bytes) -> None:
    if not isinstance(template, bytes) or not template:
        raise ValueError("Ngarko modelin bosh ToC në formatin Word.")
    if len(template) > MAX_TEMPLATE_BYTES:
        raise ValueError("Modeli ToC është më i madh se 4 MB.")
    try:
        doc = Document(BytesIO(template))
    except Exception as exc:
        raise ValueError("Modeli ToC nuk mund të lexohet si .docx.") from exc
    if len(doc.tables) != 1:
        raise ValueError("Për prototipin kërkohet modeli me një tabelë të vetme.")
    table = doc.tables[0]
    if len(table.columns) != 7 or len(table.rows) < 4:
        raise ValueError("Modeli duhet të ketë shtatë kolona dhe rreshta bosh.")
    headers = tuple(c.text.strip() for c in table.rows[2].cells)
    if headers != EXPECTED:
        raise ValueError(
            "Kokat e kolonave nuk përputhen me modelin ToC me 7 kolona."
        )
    if (
        table.rows[0].cells[0]._tc is not table.rows[0].cells[1]._tc
        or table.rows[0].cells[2]._tc is not table.rows[0].cells[6]._tc
    ):
        raise ValueError("Mungojnë bashkimet 2+5 të rreshtit hyrës.")
    for row in table.rows[3:]:
        if any(cell.text.strip() for cell in row.cells):
            raise ValueError(
                "Ngarko modelin BOSHQ, jo një ToC të plotësuar. "
                "Të dhënat e dokumentit të plotësuar nuk duhet të kopjohen."
            )


def create_toc_using_template(
    template: bytes, units: list[Provision], directive_title: str
) -> bytes:
    """Reproduce the uploaded template's styles, widths and 7-column layout."""
    validate_blank_template(template)
    if not units:
        raise ValueError("Nuk u identifikuan dispozita për tabelën.")
    if len(units) > 160:
        raise ValueError("Maksimumi 160 rreshta; zgjidh më pak nene.")
    if not directive_title.strip() or len(directive_title) > 220:
        raise ValueError("Titulli i direktivës duhet të jetë i shkurtër.")

    doc = Document(BytesIO(template))
    table = doc.tables[0]
    prototype = deepcopy(table.rows[3]._tr)
    for row in list(table.rows)[3:]:
        table._tbl.remove(row._tr)

    for unit in units:
        table._tbl.append(deepcopy(prototype))
        row = table.rows[-1]
        row.cells[0].text = unit.reference
        row.cells[1].text = unit.text
        for col in range(2, 7):
            row.cells[col].text = ""

    # Keep the original title block, merge layout, and style.
    first = next((p for p in doc.paragraphs if p.text.strip()), None)
    if first is not None:
        first.text = directive_title + " (Tabelë përputhshmërie — draft teknik)"
    table.rows[0].cells[0].paragraphs[0].text = directive_title
    right = table.rows[0].cells[2]
    for paragraph in right.paragraphs:
        if paragraph.text.strip().startswith("Shkalla e përputhshmërisë:"):
            paragraph.text = "Shkalla e përputhshmërisë: [për vlerësim juridik]"
    # Do not imply that F/P/N/N/A or national references have been decided.
    out = BytesIO()
    doc.save(out)
    result = out.getvalue()

    # Verify the seven columns and the exact extracted text carried into Word.
    check = Document(BytesIO(result)).tables[0]
    if len(check.columns) != 7 or len(check.rows) != len(units) + 3:
        raise AssertionError("ToC structure changed during DOCX generation.")
    for i, unit in enumerate(units, 3):
        if check.rows[i].cells[0].text != unit.reference:
            raise AssertionError("Provision reference changed while saving.")
        if check.rows[i].cells[1].text != unit.text:
            raise AssertionError("Provision text changed while saving.")
        if any(check.rows[i].cells[j].text for j in range(2, 7)):
            raise AssertionError("Legal assessment columns must remain blank.")
    return result
