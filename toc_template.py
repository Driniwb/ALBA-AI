"""Fill the user's blank seven-column Albanian ToC template without redesigning it.

The blank DOCX is supplied at runtime, never committed or stored server-side.
Only column 1 (provision reference) and column 2 (extracted EU text) are filled.
No national-law mapping, equivalence or legal assessment is performed.
"""
from copy import deepcopy
from io import BytesIO
import re

from docx import Document
from docx.shared import Cm, Pt
from docx.enum.section import WD_ORIENT

from toc_builder import Provision

MAX_TEMPLATE_BYTES = 4 * 1024 * 1024
EXPECTED = (
    "Neni", "Teksti", "Referenca", "Neni",
    "Përmbajtja", "Përputhshmëria", "Komente",
)



def built_in_blank_toc() -> bytes:
    """Public, synthetic seven-column ALBA template with familiar headings.

    This approximates the blank model layout but never reproduces the
    user-provided blank document. Upload that DOCX for exact styling.
    """
    doc = Document()
    sect = doc.sections[0]
    sect.orientation = WD_ORIENT.LANDSCAPE
    sect.page_width = Cm(29.7)
    sect.page_height = Cm(21.0)
    sect.left_margin = sect.right_margin = Cm(1.25)
    sect.top_margin = sect.bottom_margin = Cm(1.5)
    doc.add_paragraph("Direktiva ....... (Tabelë përputhshmërie)")
    doc.add_paragraph("")
    table = doc.add_table(rows=4, cols=7)
    table.style = "Table Grid"
    table.autofit = False
    widths = [Cm(v) for v in (1.9, 7.0, 1.5, 1.9, 6.9, 1.8, 6.1)]
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            cell.width = widths[i]
    top = table.rows[0]
    top.cells[0].merge(top.cells[1]).text = "Direktiva ......."
    top.cells[2].merge(top.cells[6]).text = (
        "Legjislacioni shqiptar i propozuar (titulli i projektaktit)\n"
        "1.1. ........\n"
        "F – Plotësisht e harmonizuar\n"
        "P – Pjesërisht e harmonizuar\n"
        "N – Pa Harmonizuar\n"
        "N/A – jo relevante për përafrim\n"
        "Shkalla e përputhshmërisë: [për vlerësim juridik]"
    )
    for cell, value in zip(table.rows[1].cells, map(str, range(1, 8))):
        cell.text = value
    for cell, title in zip(table.rows[2].cells, EXPECTED):
        cell.text = title
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(8)
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)
    out = BytesIO()
    doc.save(out)
    return out.getvalue()

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
        row.cells[0].paragraphs[0].text = unit.reference
        row.cells[1].paragraphs[0].text = unit.text
        for col in range(2, 7):
            row.cells[col].paragraphs[0].text = ""

    # Keep the original title block, merge layout, and style.
    first = next((p for p in doc.paragraphs if p.text.strip()), None)
    if first is not None:
        first.text = directive_title + " (Tabelë përputhshmërie — draft teknik)"
    table.rows[0].cells[0].paragraphs[0].text = directive_title
    if len(doc.paragraphs) > 1 and not doc.paragraphs[1].text.strip():
        doc.paragraphs[1].text = (
            "PROVË TEKNIKE: teksti i nxjerrë duhet krahasuar me burimin autentik; "
            "ndarja e dispozitave dhe përputhshmëria juridike nuk janë verifikuar."
        )
    doc.core_properties.author = "ALBA AI (prototype)"
    doc.core_properties.last_modified_by = ""
    right = table.rows[0].cells[2]
    for paragraph in right.paragraphs:
        if "Shkalla e përputhshmërisë:" in paragraph.text:
            paragraph.text = re.sub(
                r"Shkalla e përputhshmërisë:\s*F\s*\(e plotë\)",
                "Shkalla e përputhshmërisë: [për vlerësim juridik]",
                paragraph.text,
            )
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
