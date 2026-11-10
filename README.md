# ALBA AI 3.3 – Legal Writing, ToC Builder and Communication Studio

ALBA AI is an experimental assistant for Albanian legal and institutional language.

Three Streamlit pages are available from `streamlit run app.py`:

- **ALBA language editor:** existing text editor with source-traceable writing guidance.
- **Communication Studio:** create, review or adapt Albanian public communication in Press & Media (press release, press statement), Newsletter & Web (newsletter, website article) and Social Media (Instagram, LinkedIn, Facebook, X).
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

## Communication Studio (ALBA 3.3)

The new sidebar page `pages/2_Communication_Studio.py` uses two **separate** reference layers:

- `reference_library/communication_sources.csv`: 11 publicly accessible official or publisher guidance pages (European Commission, OECD, GDS/GOV.UK, Mailchimp and X) and GIZ public newsroom examples. Sources are categorised as official public guidance, vendor guidance, platform information or **illustrative examples only**. GIZ public examples **are not** an endorsement or an internal GIZ style guide.
- `reference_library/communication_rules.csv`: ALBA's **C01–C30 editorial syntheses** with format mappings, source IDs, review status and original synthetic Albanian examples. They are not quotations or legally binding rules from the named organisations.
- `reference_library/rules.csv`: selected existing Albanian-writing R-rules (including the caveat that the spelling source from 1973 is historical, not a present-day official dictionary).

Each format activates only its relevant C-rules, never the full C01–C30 list. User may select **Create**, **Review**, or **Adapt**, with an organisation, audience, objective, and optional description of visual content. An editable response is displayed with a publishing section and a separate verification section. The published content can be downloaded as a TXT file or reused as input for another communication format **within the same Streamlit session**. The tool **does not** post to social accounts, send newsletters, save uploads or require external app logins.

The AI uses the **existing Cloudflare Workers AI configuration** and requests are transmitted only after an explicit Generate action; never during page load. Do not input personal data, unpublished government or development partner documents, or confidential material. The generated text is **not approved for publication**: facts, dates, quotations, donor acknowledgement, links, consent and organisation-specific approval requirements still require human verification.

Automated editorial warning checks are intentionally limited: newly introduced numerals or URLs, possible unattributed quoted passages, lack of newsletter subject/preview text, and a simple 280-character length check for standard X posts. A successful warning check does not establish factual accuracy. X URL weighting and account-specific length allowances can differ from the simple check.

### Verification

```bash
python -m pip install -r requirements.txt 'reportlab>=4.0'
python -m unittest discover -s tests -v
streamlit run app.py
```

This work extends ALBA's communication drafting only. The existing legal editor and legal ToC translation workflows remain separate.
