"""End-to-end smoke test against a public PDF of Directive 2008/68/EC.

The source is the 27 June 2019 consolidated text archived by UK
legislation.gov.uk. It is used only for **technical extraction testing**;
not as legal authority or the version for an actual ToC.
"""
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from docx import Document
from toc_builder import extract_document, split_provisions
from toc_units import first_n_articles
from toc_template import create_toc_using_template

URL = "https://www.legislation.gov.uk/eudr/2008/68/pdfs/eudr_20080068_2019-06-27_en.pdf"

def _synthetic_blank_template():
    """A generic seven-column stand-in, NOT the user's ToC file."""
    doc = Document()
    doc.add_paragraph("Direktiva ...... (Tabelë përputhshmërie)")
    table = doc.add_table(rows=4, cols=7)
    table.rows[0].cells[0].merge(table.rows[0].cells[1]).text = "Direktiva ......"
    table.rows[0].cells[2].merge(table.rows[0].cells[6]).text = (
        "Legjislacioni shqiptar i propozuar (titulli i projektaktit)\n"
        "Shkalla e përputhshmërisë: F (e plotë)"
    )
    for cell, value in zip(table.rows[1].cells, map(str,range(1,8))):
        cell.text = value
    labels = ("Neni","Teksti","Referenca","Neni","Përmbajtja",
              "Përputhshmëria","Komente")
    for cell, value in zip(table.rows[2].cells, labels):
        cell.text = value
    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def main():
    try:
        req = Request(URL, headers={"User-Agent":"ALBA-ToC-Prototype/0.1"})
        with urlopen(req, timeout=35) as stream:
            content = stream.read(8 * 1024 * 1024 + 1)
    except Exception as exc:
        print("INCONCLUSIVE: public PDF unavailable:", str(exc))
        return

    if not content.startswith(b"%PDF"):
        print("INCONCLUSIVE: source did not return a PDF")
        return

    # Public source only. Upload as short-lived CI artifact to support an
    # actual offline local integration test with the privately held template.
    outdir = Path("artifacts")
    outdir.mkdir(exist_ok=True)
    (outdir / "PUBLIC_2008_68_EC_2019_CONSOLIDATED_TEST.pdf").write_bytes(content)

    try:
        extracted = extract_document("directive_2008_68.pdf", content)
        rows = split_provisions(extracted.text)
        names = [row.reference for row in rows]
        for expected in ("Article 1", "Article 2", "Article 3"):
            assert expected in names, f"Missing {expected}: {names[:20]}"
        a1 = next(row.text for row in rows if row.reference == "Article 1")
        a2 = next(row.text for row in rows if row.reference == "Article 2")
        a3 = next(row.text for row in rows if row.reference == "Article 3")
        assert "Scope" in a1
        assert "Definitions" in a2
        assert "General provisions" in a3
        pilot = first_n_articles(extracted.text, count=3)
        assert len(pilot) >= 3
        word = create_toc_using_template(
            _synthetic_blank_template(), pilot,
            "Directive 2008/68/EC (2019 consolidation) — TECHNICAL TEST",
        )
        output = Document(BytesIO(word))
        assert len(output.tables[0].columns) == 7
        assert len(output.tables[0].rows) == len(pilot) + 3
        assert all(not output.tables[0].rows[i].cells[k].text
                   for i in range(3,len(output.tables[0].rows))
                   for k in range(2,7))
        outdir = Path("artifacts")
        outdir.mkdir(exist_ok=True)
        (outdir / "ALBA_ToC_2008_68_Articles_1-3_7COL_DEMO.docx").write_bytes(word)
        print("Granular ToC units for Articles 1-3:",len(pilot))
        print("SUCCESS:", "PDF bytes=",len(content),"sections=",len(rows))
        print("Extracted Article 1/2/3 chars:",len(a1),len(a2),len(a3))
        print("Word bytes:",len(word))
        print("Notice: structural extraction only. Literal legal fidelity and sentence-level units require manual verification.")
        for item in extracted.warnings:
            print("WARNING:",item)
    except Exception as exc:
        print("FAILED to parse actual PDF:", repr(exc))
        raise

if __name__ == "__main__":
    main()
