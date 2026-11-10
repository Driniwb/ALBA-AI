# ALBA – Legal and Institutional Writing Toolkit

ALBA is an experimental assistant for Albanian legal and institutional language.

Launch `streamlit run app.py` for five named pages:

- **Writing Assistant:** existing text editor with source-traceable writing guidance.
- **EU Communication & Reporting:** dedicated sidebar page for Information Note, Administrative Capacity Note, Benchmark/Acquis Progress Report, Negotiating Position section and Reply to the European Commission, in English or Albanian.
- **Legal Drafting:** create, minimally amend, review or draft literal-first acquis approximations for four distinct Albanian normative act types (law, Council of Ministers decision, ministerial instruction, regulation).
- **Communication Studio:** create, review or adapt Albanian public communication in Press & Media (press release, press statement), Newsletter & Web (newsletter, website article) and Social Media (Instagram, LinkedIn, Facebook, X), plus five EU Communication & Reporting formats (English or Albanian). One button can generate separate drafts for all four social channels.
- **ToC Builder:** upload a *public or synthetic* English-language EU directive (text PDF or DOCX), select from one to eight articles, and download a **seven-column Word Table of Concordance**. A public-source synthetic template is included; the user can upload a blank 7-column DOCX to preserve the exact desired structure and style.

The ToC Builder identifies source language locally; its output depends on the detected language:

1. **English detected – literal EN–SQ legal translation (draft):** translate **one legal unit at a time** using the existing Cloudflare Workers AI Gemma 4 model and the existing Streamlit secrets. User clicks to send the next 1–4 selected units. Translation progress and edits are kept only in Streamlit session state. The Word export is enabled only when all selected units have translations. Number/reference/acronym heuristic warnings are shown, and any unit may be corrected manually.
2. **Albanian detected – preserve source text:** keep the Albanian provisions as provided and generate a ToC without an AI call. Mixed or uncertain-language documents are not silently processed.

Output columns reproduce the seven-column Albanian model: `Neni | Teksti | Referenca | Neni | Përmbajtja | Përputhshmëria | Komente`. Only the first two are filled; the national legislative reference, national clause, approximation grade F/P/N/N/A, and remarks remain **blank**. The summary at the top is clearly labelled `[për vlerësim juridik]` rather than claiming that full approximation has been established.

**Important limitations:** This is a **drafting prototype**, not a certified legal translation or a conformity assessment. Scanned PDFs are not supported; PDF text extraction may omit footnotes, misjoin words, or preserve page markers. Automated splitting at sentence level (particularly after lettered lists) is not reliable. A user **must** check each unit against the authentic, current EU publication and confirm all translated meanings, numbering and annex references. The model's translation quality has not been established by live human evaluation. The pilot supports Articles 1–8; entire directives should be handled section by section.

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


## Local privacy gate and file attachments (ALBA 3.4)

All three Streamlit modules now use \`privacy_guard.py\` before AI processing:
- **Legal & Institutional Writing:** pasted text plus optional \`.txt\`, \`.md\`, \`.docx\` or text-based \`.pdf\` supporting document.
- **ToC Builder:** existing directive PDF/DOCX and optional blank ToC DOCX are screened **before** extracting and showing legal units or calling the translation model.
- **Communication Studio:** pasted factual brief/draft and an optional text-based file in the same four formats; screened content is used to create, review or adapt the chosen communication type.

Screening is implemented with local Python patterns for possible contacts, emails, Albanian personal IDs, labeled names/birthdates, banking/credit-card numbers, passwords/API secrets, confidential/internal classification markers, personal addresses and certain health-record indicators. It stops the relevant workflow **before** Cloudflare calls and shows a *generic warning only*. AI-generated content is also screened before display and download. There is no bypass toggle in the prototype. The app does not echo matched values, snippets, file text or identifiers in the warning.

### Published normative acts: easier upload (ALBA public-law mode)

**Legal Drafting** has one public-source declaration; it no longer asks a
second question about whether the act has been formally published. Published
laws, VKMs, instructions, public consultation drafts, EU directives and
regulations may use words such as *konfidencialitet*, *medical records* and
*personal data* without being rejected just for discussing those legal
concepts. The ToC builder uses the same public normative source screen.

Readable legal PDF/DOCX documents with logos/illustrations are accepted,
but image content is **not interpreted or sent to Cloudflare**. On long acts,
the upload is read and the user selects a provision/section to send for AI
analysis; the app does **not** silently submit a truncated entire law.
Legal Drafting offers the full extracted text as a read-only reference.
Current model context limits still require working article by article.

The safeguard still rejects actual personal identifiers, private contacts,
credentials, explicit confidential-document classifications and unsupported
or scanned files, and shows a generic, actionable reason category rather
than leaking a sensitive match. Attesting "public" does not make private
documents lawful to share; this workflow is for **public/synthetic** material
only, not internal government drafts, personal case files or private records.

### Security and transparency limits

- **The file must be temporarily read by the Streamlit server to be screened.** "No AI processing" means the **blocked input is not transmitted to Cloudflare**; it does **not** mean the hosting platform has never received the uploaded bytes. The standard file uploader itself may display the filename to the submitting user. Do not upload confidential or personal information.
- Heuristic text patterns **cannot reliably detect every person, sensitive fact or indirect identifier**, and they can flag benign text. This is a precaution, **not a certified GDPR compliance solution, redaction solution, DLP system or guarantee of data confidentiality**.
- Encrypted, image-only/scanned, password-protected and uninspectable files remain blocked. Published legal PDFs and DOCX files with logos/images are now accepted **when their text can be extracted**, with an explicit warning that non-text diagrams/annexes were not read by ALBA. Ordinary uploads are limited to 4 MB; public legal uploads are allowed up to 12 MB and 180 PDF pages. Documents with embedded executable objects remain blocked. Text sent to the AI is bounded per module.
- File bytes are not intentionally stored in a database or GitHub repository by ALBA. The Streamlit app framework and host receive uploads and may have their own logging and retention practices; these have **not** been independently audited.
- For the public pilot, users should still use **only public or synthetic examples**, with no identifying details. High-assurance use with confidential government or partner documents would require separate infrastructure, a fuller data-protection assessment, role-based controls, encryption, logging policy and explicit approval.
- Existing ToC splitting and AI translation remain drafts requiring source-by-source expert verification.

Run tests with \`python -m unittest discover -s tests -v\`. All privacy fixtures are synthetic. The app does not auto-publish communications or send any message.

## ALBA 3.5 – unified English UI and visual system

All three Streamlit pages now present **navigation, field labels, actions, warnings, upload prompts, privacy notices and status information in English**.
The generated legal and institutional drafts remain **in Albanian**. UI language and document-output language are separate; original-source review remains available for legal verification.

The main writing page no longer displays the raw reference library or retrieved rule IDs. Communication Studio does not display the active communication rules or source-library links. The writing backend still uses R-rules and format-specific C-rules internally. ToC retains its source-language and translation review functions.

The common `ui_theme.py` and `.streamlit/config.toml` use the [2 Bit Matrix palette](https://lospec.com/palette-list/2-bit-matrix): `#f2fff2`, `#add9bc`, `#5b8c7c`, `#0d1a1a`, plus a restrained terracotta accent (`#d57847`). No images, external font files or trackers are introduced.

Internal Albanian error messages are surfaced as English messages through `ui_copy.friendly_error` without displaying source snippets or compromising the preexisting privacy gate.

## ALBA branding and design update

The product name displayed in Streamlit is now **ALBA** (no trailing AI). The default navigation item is explicitly **Writing Assistant** rather than the entrypoint filename "app". Other navigation entries are ToC Builder and Communication Studio. This uses a Streamlit `st.navigation` router and named `st.Page` scripts.

The previously visible sentence directing readers to explore other pages is removed from the Writing Assistant. The **Directive title** field in ToC Builder is intentionally **empty until entered** by the user. The article selector supports the first **1 through 8** articles (default: first 3). Both modes still require verification of extraction and literal Albanian translation against official legal sources.

The shared interface now takes inspiration from 1950s–1960s **atomic-age retro-futurist editorial and analogue control-panel styling**, familiar from the Fallout TV series' set design, without borrowing its logos, artwork, proprietary fonts or imagery. Original CSS-only concentric dials and restrained mechanical details use aged ivory, olive and teal surfaces, brass amber and rust accents. Responsive layout and readable text remain priorities.

**Usage data:** No hidden harvesting of prompts, uploads or AI-generated material was added. Streamlit `gatherUsageStats = false` remains set. Any future product analytics should be limited, documented and transparent, with opt-in collection for substantive feedback and no covert retention of user content.

## Source-language recognition and social post styles

ToC Builder no longer asks the user to choose between **"Literal Albanian translation (AI)"** and **"Original text (no translation)"**. A deterministic, local language detector (`toc_language.py`) uses legal vocabulary and headings to identify English and Albanian text. English units are queued for user-triggered literal translation; already-Albanian units are preserved and exported in Word. When the language is uncertain or mixed, ALBA stops and asks the user to provide a clear source; it must not guess or silently transmit unclassified text. The directive title starts blank. Detection is heuristic and does **not** certify the original source or its legal accuracy.

Communication Studio adds two optional post styles to Instagram, LinkedIn, Facebook and X only: **Elevator pitch – concise & compelling**, and **Elevated editorial – polished & understated**, alongside the existing platform-appropriate default. Elevator pitch uses a factual hook, meaningful value and a call to action only if there is a real next step in the source. Elevated editorial uses a refined, restrained professional style without hyperbole. Both preserve platform-specific requirements, source facts, and the existing personal-data screening; only user-triggered Generate sends screened text to the external model. Press releases, press statements, website articles and newsletters are unaffected by these social styles. Automated output requires editorial review before publication.


## Legal Drafting and EU Communication & Reporting (pilot)

The fourth page, `pages/3_Legal_Drafting.py`, uses `legal_drafting.py` and curated public methodological pointers in `reference_library/legal_drafting_sources.csv`. It separates four act types: **draft law, draft Council of Ministers decision, draft ministerial instruction and draft regulation**. Each act has its own drafting guidance, delegated-authority checks and expected normative structure. Modes: **new drafting, minimal amendment, legal-technique review and literal-first EU acquis approximation**. Amendment work must identify the existing provision; acquis work requires the relevant EU provision supplied by the user. ALBA will not invent enabling legislation, institutions, sanctions, accession effects or full approximation grades. Every AI response separates proposed text from outstanding legal checks. Output is an editable draft and a TXT download, not an officially verified legal instrument.

Within **Communication Studio → EU Communication & Reporting**, the supported categories are **Information Note, Administrative Capacity Note, Benchmark/Acquis Progress Report, Negotiating Position section and Reply to the European Commission**. Output may be **English or Albanian**. Editorial guidance draws on public EU assessment and Transport Community reporting examples, catalogued in `reference_library/eu_reporting_sources.csv`; **these are reference examples, not mandatory templates** or evidence of any institution's achievements. Prompts require clear separation of enacted versus draft legislation, legal alignment versus implementation/enforcement, confirmed versus planned staff/FTE, results versus targets and measurable commitments versus aspirations. The output always includes a draft-for-transmission section plus a separate pre-submission verification section. Drafts need substantive institutional review, source checking and approval.

Public-media C-rules and historic Albanian editorial rules are not applied to the EU reporting prompt; this prevents social-media or newsletter style guidance from contaminating reporting outputs. The four-platform social bundle remains an independent action with four separately generated, editable drafts; it does not post anything online. The public pilot's privacy restrictions apply equally to these new functions: **use public or synthetic material only**. Documents and AI output are screened locally with imperfect heuristics; screening does not guarantee confidentiality or data-protection compliance. Cloudflare Workers AI receives selected text on explicit generation requests.

### QA and release

Run `python -m unittest discover -s tests -v` and check each Streamlit page. Unit tests use only synthetic fixtures and mocked calls; they validate prompt routing and UI smoke cases, **not** the legal accuracy or quality of live model-generated drafts. These modules are included in `main`; changes are checked in development branches before merging.

## Automatic Cloudflare-only independent review (experimental)

ALBA uses the **existing Cloudflare Workers AI account and token only**. No
Google AI Studio, OpenRouter, Hugging Face or second set of API credentials is
required. The original Gemma 4 draft generation is unchanged.

Once a legal or EU reporting draft is prepared, the user may click **Run ALBA
independent review**, after explicitly consenting to the additional processing
of public/synthetic material inside Cloudflare. ALBA automatically decides
whether to run **GLM-4.7-Flash** alone or both **GLM-4.7-Flash** and
**Qwen 3.8 27B**, based on the legal/document risk. There is **no user model
selection**. Source, draft and EU provisions are supplied to each independent
reviewer. Review findings and defensible old/new formulations are displayed
separately. These are not merged, ranked by votes, applied to drafts, or
claimed as certification. Missing evidence or conflicting legal readings must
be decided by a human expert.

* Source references: Cloudflare's current model catalog confirms
  `@cf/zai-org/glm-4.7-flash` and `@cf/qwen/qwen3.8-27b`.
* Workers Free allows **10,000 shared Neurons per day** for drafting and
  reviewing combined. Once exhausted, new operations fail until the daily
  reset. Workers Paid accounts may incur additional charges beyond this
  allocation. The review UI is disabled unless the app administrator has
  **positively verified** that the account is on Workers Free.
* Requests are made only after the user clicks Review. Failed model calls
  never trigger a paid service, a hidden retry, or a third-party API.
  Successful partial results remain visible when another reviewer fails.
* Work exclusively with **public or synthetic** texts. The source and draft
  are screened with conservative local patterns, but those do not guarantee
  that no confidential or identifying data will pass. Only approved public
  workflows should be used at this stage.

### Streamlit configuration

The existing values remain:

```toml
CLOUDFLARE_ACCOUNT_ID = "..."
CLOUDFLARE_API_TOKEN = "..."
```

After verifying your Cloudflare account is on **Workers Free**, add:

```toml
CLOUDFLARE_FREE_PLAN_CONFIRMED = true
```

This flag is an administrator assertion, not a cryptographic or API-backed
billing check. Leave it unset on Workers Paid if you require a hard
**no-overage** policy. Do not store tokens in GitHub or expose them in chat.

### Validation and limitations

`tests/test_cloudflare_review.py` exercises deterministic routing, both
model IDs, source and draft handling, response validation, privacy preflight,
quota failures and Streamlit page loading with **mocked API responses**.
GitHub Actions CI runs the full local tests. This does not assess live
model availability or the actual legal quality of GLM/Qwen-generated review.
Always verify literal transposition, legal basis, annex applicability,
institutional responsibilities, dates, figures and adoption status manually.
