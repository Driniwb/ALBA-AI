# ALBA AI – seven-column Word ToC builder (isolated proof of concept)

**Status:** technical test branch, NOT merged into the deployed ALBA 3.1 application.

The proof of concept accepts (1) a public or synthetic, text-based EU directive PDF/DOCX and (2) a **blank seven-column Albanian ToC Word template** at runtime. It produces a Word table based on the supplied template. The actual user-supplied draft and filled Table of Concordance were **not uploaded or copied to this public repository**. The published tests construct their own synthetic blank model.

## Run the preview

```bash
python -m pip install -r requirements.txt
streamlit run toc_demo.py
```

Choose 1–8 articles (three by default), provide a concise title, review the extracted references, and download the draft ToC in Word.

The prototype preserves the source template's merged top row, seven-column headings, table grid and available style elements. It removes the model's advance claim of full legal approximation, replacing the summary with `[për vlerësim juridik]`. It fills **only column 1 (Neni)** and **column 2 (Teksti)**. Columns 3–7 are deliberately blank, including the national reference, national provision, degree F/P/N/N/A, and Remarks.

## Reference model characteristics (screened privately)

- Landscape A4, one seven-column table.
- First row: merged cells spanning columns 1–2 and 3–7.
- Second and third rows: numbered columns 1–7 and the exact headings: `Neni | Teksti | Referenca | Neni | Përmbajtja | Përputhshmëria | Komente`.
- A completed example had 289 table rows, 286 of which were substantive; it includes examples of paragraph, letter and sometimes sentence-level segmentation. **The example's legal mappings, compliance grades and internal legal commentary are not imported.**
- A source article/paragraph is not necessarily paired with a national provision of the same number; those alignments must be made by a legal specialist.

## Technical and legal limitations

- Word DOCX is the output. There is **no spreadsheet export**.
- No AI model is used in the current builder; no translation or national transposition assessment is made.
- The PDF text extraction may change line wrapping and ordering or omit image-only pages, figures and footnotes. Scanned PDFs are not supported. Word-generated list numbering can be absent from extracted text.
- Article, paragraph and letter markers are recognised only when sufficiently explicit. Annexes remain separate; not all subunits, especially separate sentences in a single provision, are reliably recognised. Check every line against the authentic version.
- The output is **not certified as a literal transcription**. Manual verification of completeness, numbering and wording is mandatory.
- A completed ToC file cannot be uploaded as a template; the builder validates that the national-law and grading columns in the supplied Word template are blank.
- The publicly sourced integration test uses an archived **2019 consolidated version** of Directive 2008/68/EC to check functionality, **not as the current legal source**. The Word artifact published by GitHub Actions uses a generated synthetic template, not the user-supplied blank DOCX.
- Use only public or synthetic uploads. The prototype remains separate from the public ALBA 3.1 deployment until functional, confidentiality and rendering quality tests are completed.

## Verification

```bash
python -m unittest discover -s tests -v
```

The GitHub Actions workflow `ToC Word proof of concept` also checks a publicly accessible, text-based PDF of Directive 2008/68/EC (when available) and produces a short-lived Word test artifact for Articles 1–3.
