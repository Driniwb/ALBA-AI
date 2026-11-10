# ALBA AI 3.2 – Word ToC Builder and literal translation

ALBA AI is an experimental assistant for Albanian legal and institutional language.

Two Streamlit pages are available from `streamlit run app.py`:

- **ALBA language editor:** existing text editor with source-traceable writing guidance.
- **ToC Builder:** upload a *public or synthetic* English-language EU directive (text PDF or DOCX), select up to three articles, and download a **seven-column Word Table of Concordance**. A public-source synthetic template is included; the user can upload a blank 7-column DOCX to preserve the exact desired structure and style.

The ToC Builder has two distinct modes:

1. **Literal EN–SQ legal translation (draft):** translate **one legal unit at a time** using the existing Cloudflare Workers AI Gemma 4 model and the existing Streamlit secrets. User clicks to send the next 1–4 selected units. Translation progress and edits are kept only in Streamlit session state. The Word export is enabled only when all selected units have translations. Number/reference/acronym heuristic warnings are shown, and any unit may be corrected manually.
2. **Original-source text:** preserve the extracted source language for technical comparison, without an AI call.

Output columns reproduce the seven-column Albanian model: `Neni | Teksti | Referenca | Neni | Përmbajtja | Përputhshmëria | Komente`. Only the first two are filled; the national legislative reference, national clause, approximation grade F/P/N/N/A, and remarks remain **blank**. The summary at the top is clearly labelled `[për vlerësim juridik]` rather than claiming that full approximation has been established.

**Important limitations:** This is a **drafting prototype**, not a certified legal translation or a conformity assessment. Scanned PDFs are not supported; PDF text extraction may omit footnotes, misjoin words, or preserve page markers. Automated splitting at sentence level (particularly after lettered lists) is not reliable. A user **must** check each unit against the authentic, current EU publication and confirm all translated meanings, numbering and annex references. The model's translation quality has not been established by live human evaluation. The first pilot is limited to Articles 1–3; entire directives should be handled section by section.

**Privacy:** The repository is public. No user-uploaded blank or completed ToC was committed. The built-in template is generated synthetically from general seven-column characteristics. Do not upload internal government/partner drafts, non-public legal documents, confidential notes, sensitive data, or personal information. When a user clicks translation, selected text is transmitted to **Cloudflare Workers AI**, an external AI service. Original file bytes are not sent as files; working data and progress are held in the Streamlit process/session, not a persistent database.

## Run locally

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Configure `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in Streamlit secrets. Do not place these credentials in the repository. Static and mocked tests run with:

```bash
python -m unittest discover -s tests -v
```

The optional `ToC Word proof of concept` workflow on the original development branch also checks source extraction against a public archive of Directive 2008/68/EC; it does not certify legal-language fidelity.
