"""End-to-end smoke test against a public PDF of Directive 2008/68/EC.

The source is the 27 June 2019 consolidated text archived by UK
legislation.gov.uk. It is used only for **technical extraction testing**;
not as legal authority or the version for an actual ToC.
"""
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen
from docx import Document
from toc_builder import extract_document, split_provisions, to_word

URL = "https://www.legislation.gov.uk/eudr/2008/68/pdfs/eudr_20080068_2019-06-27_en.pdf"

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
        pilot = [row for row in rows if row.reference in {"Article 1", "Article 2", "Article 3"}]
        assert [p.reference for p in pilot] == ["Article 1", "Article 2", "Article 3"]
        word = to_word(pilot, "Directive 2008/68/EC (2019 consolidation) — technical test ONLY")
        output = Document(BytesIO(word))
        assert len(output.tables[0].rows) == 4
        assert [output.tables[0].cell(i, 0).text for i in range(1,4)] == ["Article 1", "Article 2", "Article 3"]
        outdir = Path("artifacts")
        outdir.mkdir(exist_ok=True)
        (outdir / "ALBA_ToC_2008_68_Articles_1-3_TECHNICAL_TEST.docx").write_bytes(word)
        print("SUCCESS:", "PDF bytes=",len(content),"sections=",len(rows))
        print("Extracted Article 1/2/3 chars:",len(a1),len(a2),len(a3))
        print("Word bytes:",len(word))
        print("Notice: this validates article boundaries, not sub-point row separation or literal fidelity.")
        for item in extracted.warnings:
            print("WARNING:",item)
    except Exception as exc:
        print("FAILED to parse actual PDF:", repr(exc))
        raise

if __name__ == "__main__":
    main()
