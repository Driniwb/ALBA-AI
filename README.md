# ALBA – Legal and Institutional Writing Toolkit

## ALBA 2.0 — unified Projects & Chats interface (November 2026)

On `develop/alba-v2`, the default workspace has a redesigned, original
light legal-research interface inspired by the clean layout of EU-law AI
products: white reading canvas, soft grey sidebar, navy/blue controls, and
a centered empty-chat welcome.

The **only sidebar content sections** are **Projects** and **Chats**,
with New chat, search, and optional backup/restore actions. Previous standalone
Writing Assistant, ToC Builder, Legal Drafting, RIA Builder, and EU Reporting
pages are **registered but hidden**, not deleted. The chat no longer shows
their shortcut cards or "Continue in ..." handoff prompts. Document upload
uses the chat input's native **+**, with public PDF/DOCX/XLSX/PPTX files
screened before model requests. Answer style, jurisdiction scope, and
project creation are accessible via compact chat composer controls. The
optional sources panel starts closed and offers navigational references
without claiming that legislation has been independently retrieved.

**Scope:** This is a UI/conversational consolidation, not feature parity with
eulaw.ai. The old structured seven-column ToC Word builder, live primary-source
retrieval, persistent indexed document library, and cross-device account
storage are **not** made available inside unified chat by this design change.
The chat can draft from supplied public excerpts and export answers as Word,
but does not have a verified live EU/legal search backend. Streamlit Cloud
deployment and end-to-end browser behavior must be checked on the actual
deployed `develop/alba-v2` app. No existing `main` deployment is modified.

ALBA is an experimental assistant for Albanian legal and institutional language.

Launch `streamlit run app.py` for six named pages:

- **Chat Workspace:** ChatGPT-style multi-turn conversations, conversation history, project folders, rename/move/delete/export controls. Guest chats are saved in the same browser through localStorage (public/synthetic only); verified sign-in + hosted PostgreSQL enables durable, owner-isolated cross-device history.
- **Writing Assistant:** existing text editor with source-traceable writing guidance.
- **EU Communication & Reporting:** dedicated sidebar page for Information Note, Administrative Capacity Note, Benchmark/Acquis Progress Report, Negotiating Position section and Reply to the European Commission, in English or Albanian.
- **Legal Drafting:** create, minimally amend, review or draft literal-first acquis approximations for four distinct Albanian normative act types (law, Council of Ministers decision, ministerial instruction, regulation).
- **Communication Studio:** create, review or adapt Albanian public communication in Press & Media (press release, press statement), Newsletter & Web (newsletter, website article) and Social Media (Instagram, LinkedIn, Facebook, X), plus five EU Communication & Reporting formats (English or Albanian). One button can generate separate drafts for all four social channels.
- **ToC Builder:** upload a public English- or Albanian-language EU directive (PDF/DOCX); ALBA structures its provisions and exports the seven-column Word Table of Concordance. English documents use one-click literal Albanian translation, while Albanian documents are exported directly. The supplied blank/filled ToC informed the built-in seven-column structure; its original binary styling is not embedded in this repository.

The ToC Builder identifies source language locally; its output depends on the detected language:

1. **English detected – literal EN–SQ legal translation (draft):** translate **one legal unit at a time** using the existing Cloudflare Workers AI Gemma 4 model and the existing Streamlit secrets. User clicks to send the next 1–4 selected units. Translation progress and edits are kept only in Streamlit session state. The Word export is enabled only when all selected units have translations. Number/reference/acronym heuristic warnings are shown, and any unit may be corrected manually.
2. **Albanian detected – preserve source text:** keep the Albanian provisions as provided and generate a ToC without an AI call. Mixed or uncertain-language documents are not silently processed.

Output columns reproduce the seven-column Albanian model: `Neni | Teksti | Referenca | Neni | Përmbajtja | Përputhshmëria | Komente`. Only the first two are filled; the national legislative reference, national clause, approximation grade F/P/N/N/A, and remarks remain **blank**. The summary at the top is clearly labelled `[për vlerësim juridik]` rather than claiming that full approximation has been established.

**Important limitations:** This is a **drafting prototype**, not a certified legal translation or a conformity assessment. Scanned PDFs are not supported; PDF text extraction may omit footnotes, misjoin words, or preserve page markers. Automated splitting at sentence level (particularly after lettered lists) is not reliable. A user **must** check each unit against the authentic, current EU publication and confirm all translated meanings, numbering and annex references. The model's translation quality has not been established by live human evaluation. The expanded pilot accepts up to 120 articles and 750 legal-unit rows, subject to document, model and quota limits. Large directives should be translated in batches and checked article by article.

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

The previously visible sentence directing readers to explore other pages is removed from the Writing Assistant. The **Directive title** field in ToC Builder is intentionally **empty until entered** by the user. The article selector supports the first **1 through 120** articles (default: first 20). Both modes still require verification of extraction and literal Albanian translation against official legal sources.

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


## Easier public-document use across ALBA

The **Writing Assistant**, **Communication Studio** and dedicated **EU
Communication & Reporting** page now share the same public-document upload
workflow as the **Legal Drafting** module. A user may upload a readable,
public PDF/DOCX with an official logo or a figure, and ordinary references
to confidentiality, medical records, privacy or legislation do not trigger
a hard block on their own. PDF diagrams and embedded graphics are *not*
interpreted or sent to the AI model.

If a source exceeds the selected AI context window, the app reads and screens
the source and opens an editable **Excerpt / article(s) to include** field,
with a separately displayed read-only extracted text for selection. The
default excerpt is explicitly identified as the opening of the document,
**not** the whole law or report. No silent truncation, model calls before
clicking Generate/Analyse, or extra external API credentials.

The **ToC Builder** accepts public EU directives and logo-bearing blank
DOCX templates using the same public-law privacy screening. It retains its
one public-material declaration and its current article-by-article ToC limits.

Real email addresses, private identifiers, filled patient records,
credentials, confidential-document classifications, unreadable or
image-only documents remain blocked, even when described as public.
The safeguard is heuristic and cannot prove whether an attachment is
actually public. The user remains responsible for selecting only genuinely
public or synthetic materials suitable for external model processing.

Regression coverage: `tests/test_public_document_modules.py`, plus
`tests/test_public_legal_uploads.py`, validates public-topic vocabulary,
mocked model generation, UI page loading and private-data blocking.

## Chat Workspace: projects, saved chats and continuing conversations

The new default navigation page is **Chat Workspace**. It reuses the existing
Cloudflare Workers AI Gemma model to answer follow-up questions with selected
recent chat turns. It supports:

- **New chat**, **continue previous chat**, named chat history in the sidebar,
  separate specialist modes (general, legal drafting, EU reporting, communication).
- **Project folders**: create a project and assign/move conversations to it.
  Removing a project unassigns its chats; it does not destroy them.
- Rename chat, delete chat (explicit confirmation), export the visible
  conversation as Markdown for personal review.
- Source-grounded legal guidance (literal-first transposition, no invented
  institutional evidence). The entire chat stays viewable; the model receives
  up to 12 recent messages (6 exchanges) within a 15,000-character budget.

### Persistence and user separation

**Without a cloud database:** The page is usable immediately for public/
synthetic conversations. A native Streamlit Component v2 stores a checked
snapshot in **this browser's localStorage**, allowing conversations and
projects to reappear after a refresh, reopening the same site, or a
Streamlit redeploy on the same origin, provided browser storage is available.
No OIDC or external PostgreSQL key is needed for that basic persistence.

**Browser storage is not an account.** History remains on this device only;
it is **not encrypted**, not private on shared computers, and is lost if the
browser clears site data, blocks localStorage or changes the app origin.
The app displays a warning if the browser cannot save history. All guest
messages remain public/synthetic only, and exportable JSON backups are still
recommended for important work. The browser snapshot has strict size limits
(1.8 MB, 80 chats, 500 messages); explicit JSON backup can exceed these
limits one conversation at a time.

**With configuration:** Chat Workspace stores conversations in a **hosted
PostgreSQL database**, isolated by a pseudonymous owner key derived from
verified OpenID Connect (OIDC) `issuer + subject` claims. Every read/write,
project move and deletion checks the owner ID; no raw email or name is saved.
Only signed-in users access PostgreSQL; unauthenticated guests never read or
write to that shared database.

1. Provision a TLS-enabled PostgreSQL database, with an account allowed to
   create the `alba_projects`, `alba_conversations` and `alba_messages`
   tables. Set `ALBA_DATABASE_URL` in Streamlit Cloud secrets.
2. Configure an OIDC identity provider, such as Google identity, Microsoft
   Entra or Auth0. Add the `[auth]` and provider-specific secrets described
   in `.streamlit/secrets.example.toml`. Register the exact callback URL
   `https://YOUR-APP.streamlit.app/oauth2callback` with the provider.
3. Restart the Streamlit app, sign in, and check that Chat Workspace displays
   **Saved workspace**. Create a conversation; sign out and sign back in to
   verify you can resume it.

The database URL and OIDC credentials must **never** be committed to GitHub
or displayed in UI/logs. A `.gitignore` now protects local secrets and
development database files. Cloud-based local SQLite files are not durable.
Avoid granting the database user more privileges than needed; enable provider
backups and at-rest encryption per organizational requirements.

**Security and scope:** This remains a **public/synthetic-only prototype**.
Heuristic filters block common personal identifiers, contact addresses,
secrets and classified markers, but cannot prove material is public. Even
when a durable database is configured, do not use the tool for non-public
institutional drafts or personal data without a separate confidentiality,
access-control and retention assessment. Database contents are not
end-to-end encrypted by ALBA. The prototype does not import older ChatGPT
chats, nor chats created on other ALBA pages. Those workflows are preserved
and can be connected to the workspace later.

**Architecture:** `chat_store.py` implements independent storage and
ownership rules; `chat_backend.py` implements the model/context boundary;
`pages/5_Chat_Workspace.py` is only the current Streamlit presentation.
The store and chat service can later be exposed through FastAPI and a React
interface without rewriting core conversation persistence.

**Offline acceptance tests:** `tests/test_chat_store.py` exercises
restart continuity, ownership isolation, project moves and deletions,
and `tests/test_chat_backend.py` covers multi-turn context, privacy
preflight, single Cloudflare requests and quota limits. These use synthetic
materials and mocked network responses, not live model calls.

### Chat Workspace audit update – persistence and restoration

The following safeguards were added after an independent code review:

- **No silent data loss:** when an OIDC-authenticated saved workspace has a
  configured PostgreSQL database but that database is unavailable, ALBA
  displays an explicit error and stops chat operations. It does *not* create a
  misleading temporary conversation in its place.
- **Stale login prevention:** verified OIDC issuer and subject are required,
  and the stored OIDC identity token's expiry/not-before/issuance claims are
  checked at the start of saved-workspace access. Streamlit documents that
  it does not automatically enforce token expiry.
- **Transport encryption:** PostgreSQL connections use TLS `sslmode=require`
  at minimum. Providers supporting `sslmode=verify-full` should use the
  stronger setting (certificate and host verification). The app does not
  claim end-to-end or application-level database encryption.
- **Safer saved metadata:** saved project names, conversation titles and
  user/assistant exchanges are screened for identifiable/private material.
- **Manual continuity without a cloud database:** download a **resumable
  chat backup (.json)** from any existing ALBA Chat Workspace conversation.
  In a new browser session, use **Restore conversation from backup** to
  import that file and continue the conversation. The JSON contains no
  account IDs or credentials. It is not encrypted. Keep downloaded backups
  private, delete them when no longer needed, and never import files from
  untrusted sources.
- **Strict import:** backup files must match the published ALBA JSON schema,
  have complete alternating conversation exchanges, be no larger than 2 MB,
  contain at most 300 messages and pass the public/synthetic safety gate.
  Restores are transactional and create new IDs owned by the current user.

**Deployment status:** Code merge + mocked CI does not activate identity
provider credentials, provision a database or validate production persistence.
The prototype now has same-browser automatic local history without account
configuration. Private, centrally controlled **cross-device** automatic
history still requires hosted PostgreSQL and a verified OIDC provider.
Neither service was provisioned by the code change.
The QA suite now exercises Streamlit chat-input interactions and multi-turn
context with mocked model responses, in addition to SQLite persistence.
A live Cloudflare response, real external PostgreSQL failover and actual OIDC
login are still separate production-acceptance tests.

### Chat usability and browser persistence fix

- **Ask ALBA is conversational and ready to use** as soon as the existing
  Cloudflare credentials are available. Pressing Send is the explicit
  user action authorising processing of public or synthetic material;
  there is no separate checkbox blocking the composer. A missing
  Cloudflare key is flagged clearly before an attempted request.
- **Test AI connection** sends only a short synthetic ping to Cloudflare;
  it does not send an uploaded document or conversation history.
- Failed questions remain visible with **Retry this question** and **Discard**
  controls. Errors distinguish missing/invalid credentials (401/403), rate
  limits (429), oversized/invalid requests, provider outages and network
  failures. A one-time fallback to Cloudflare's free GLM model is permitted
  only for primary model outages (404/5xx), never credential or quota errors.
- Local browser backup uses an official Streamlit Component v2 with fixed
  JavaScript (no model text or user source inserted into executable code).
  All restored JSON is screened, bounded and mapped to new current-session
  identifiers. The CI suite tests backend snapshots and mocked UI but cannot
  execute real browser localStorage scripts; run an actual browser refresh
  acceptance test after the Streamlit deployment.
- Streamlit 1.60 or newer is now required for this browser component.
  This does not introduce React, FastAPI, additional AI API credentials or
  a hosted database for same-browser usage.

### Natural conversations and public source attachments

ALBA Chat Workspace now answers ordinary legal and institutional questions
directly rather than always insisting on a source file or returning only
verification warnings. For generic explanations, general model knowledge
may be used; authoritative, precise legal citations still require checking
official versions. The assistant continues the current thread using the last
relevant exchanges. Specialisms remain optional, and the general assistant
handles legal drafting, policy, reporting and communication requests.

For document-grounded questions, open **Add a public document to your
question (optional)** and attach a readable public PDF, DOCX, TXT or MD.
For longer documents select up to 3,200 characters of relevant provisions.
Only the screened excerpt is appended to the question and sent to Cloudflare;
the original file is never uploaded to the model by this feature. The
attached excerpt is retained as part of the conversation and can inform
follow-ups while it remains in the context budget. The file selector resets
after a successful answer to prevent inadvertent duplicate submissions.
PDF images and scanned pages are still not interpreted here.

**Live validation remains necessary:** The new behaviour has simulated
Cloudflare and headless Streamlit tests. It has not been verified with a
real production Cloudflare token or with browser-localStorage JavaScript
executing in the user's deployed browser. The AI connection diagnostics
panel can distinguish those external-provider failures.

### Clearer Writing Assistant and EU Reporting choices

**Writing Assistant** now separates the document's format from the action
being performed. Its task choices are editing Albanian, formal adaptation
from English, terminology review, or drafting a document from supplied notes.
"Draft an email" and "prepare meeting minutes" are no longer duplicated in
the task field: choose **Institutional email** or **Meeting minutes** as the
format and **Draft a document from notes** as the action instead. Legal acts
and ToC documents remain available for *language review only* here; use
their specialised modules for substantive drafting. Audience preferences
are available under an optional section.

**EU Communication & Reporting** is now the sole entry point for all five
EU report/document formats. The duplicate category has been removed from
Communication Studio without removing the underlying EU drafting APIs.
Its two actions are **Prepare or adapt a document** (including an existing
draft as a source) and **Review an existing draft**. Institution, recipient
and objective fields remain supported under **Optional reporting details**.
Existing source, language, public-data consent, evidence checks and
Cloudflare generation logic are retained.


### Simplified conversational handoff

Chat Workspace now shows only New Chat, recent conversation history, a
message composer, optional public-document attachment, **Move to project**, and visible **Projects** folders in the sidebar
(with a Create project option inside the same control). Long-form history
management, backup import/export, language mode selection and connection
diagnostics are no longer on the chat screen; existing backend safety and
storage logic is unchanged. Other ALBA modules remain available in the
main navigation.

When the latest chat request explicitly asks for a specialised document
or workflow, ALBA offers one discreet **Continue in [module]** action.
Clicking this action opens the relevant existing form and carries forward
the question and selected public source excerpt (within that form's context
limit). This supports Legal Drafting, EU Reporting, Communication Studio,
Writing Assistant and ToC Builder. The ToC Builder still requires the user
to select an actual directive file; Streamlit file uploads cannot be moved
silently between pages. A general informational question never forces a
redirect. Navigation is user-initiated, not an extra Cloudflare API call.

## ToC Builder: broader Word exports and embedded source pictures (November 2026)

The ToC Builder now removes the **Characters** diagnostic column from the
preview and generates the same standard **seven-column** Word ToC. The
article heading and title stay with the **first substantive row** (for
example, reference `1` with `Article 1 / Purpose / 1. ...` in column 2),
instead of creating an extra `Neni 1 (hyrja)` row. Point 2 and letters
remain on separate rows with references `1.2`, `1.2.a` etc. The
full text is preserved across those units; no legal equivalence is inferred.

The new input bounds allow up to 120 articles, 750 ToC rows, 180 PDF pages,
12 MB source files and 240,000 extracted characters, provided the public
document passes existing security screening. The Cloudflare translator
still caps each *request* at 4,200 characters; a legal unit longer than
that is divided into complete, consecutive source chunks (up to 40,000
characters per unit), and its result requires expert review. A large
number of translated units can exhaust free quota; this is not a
promise of unlimited cost-free translation.

Pictures in supported formats (PNG/JPEG and other compatible raster
formats) from DOCX, or extractable PDF page images, are inserted in the
corresponding Word ToC text cell when feasible. Source image pixels are
not regenerated. The original DOCX template's logos are preserved.
Pixel placement from PDF is approximate; vector illustrations, charts,
embedded objects and unsupported pictures may require the author to
convert the source figure to PNG or revise the ToC manually. An image
retention failure must produce an explicit error, not a falsely
successful export. No OCR is performed.

The chat assistant is also aware of the actual ALBA modules: when
asked how to build a ToC, it first explains the *Table of Concordance*
workflow in ToC Builder, not Word/Google Docs' table of contents. Users
can click the matching **Continue in** action to open a module.

## One-upload ToC Builder (simplified workflow)

The active **ToC Builder** now has one visible input: **Ngarko direktivën**
(PDF or DOCX). It automatically detects English or Albanian, extracts the
whole directive within capacity bounds and structures it into the familiar
seven columns. The article number and title are joined with the first
substantive paragraph, while subsequent paragraphs and letters keep their
own references. Introductory text and annexes are included; they are not
silently removed just because the user did not select an article range.

- **Albanian input**: a Word download is immediately available without AI.
- **English input**: a single **Krijo ToC në Word** action explicitly starts
  the existing Cloudflare translator, which processes sequential units
  automatically and persists intermediate results in the current session.
  If quota/service errors interrupt translation, **Vazhdo konvertimin**
  resumes from already completed units. Once finished, download the
  Albanian Word ToC.
- **The Word format is built in:** users no longer upload an empty template,
  choose article counts, set a language switch, edit each translation in
  a separate screen, or click multiple translation batches.
- National-law mapping, compliance grades and comments are deliberately
  blank. The result is **not** a certified translation or transposition
  assessment and requires verification against the EU source.
- Source logos/images are included where the supported extraction permits.
  For PDF, image location can be approximate and vector drawings may not
  transfer as originals.

The original user-supplied ToC blank and completed sample are available as
indexed content rather than exportable raw DOCX bytes in this workspace.
The repository's built-in template reproduces the **identified seven-column
structure**; it should not be described as a byte-identical copy of the
user's original Word template. If the exact binary template becomes available
for authorized reuse, it can be embedded as the bundled baseline without
adding a second user-facing upload step.

## Chat Workspace: browser autosave repair (November 2026)

Guest Chat Workspace now mounts a single stable Streamlit component v2
browser bridge near the **start** of the page. It first reads
`localStorage["alba-public-workspace-v1"]` on the current app origin,
restores projects, ordered conversations and the most recently active chat,
then permits writes. The existing storage key and JSON version remain
compatible with earlier ALBA browser snapshots; malformed existing history
is **never overwritten**.

A submitted public/synthetic question is saved **before** the Cloudflare
request and only sent after the browser confirms the exact snapshot
revision by reading it back. A connection failure can therefore restore
the unanswered question with a **Retry** option on the next session.
Successful exchanges and project changes are saved automatically after
their server-side commit. The UI warns when saving is blocked, full or
unconfirmed rather than silently suggesting that in-memory work is durable.

The same-browser persistence is **not** equivalent to encrypted or
cross-device ChatGPT account history. Clearing browser storage, switching
browser/device, changing the app origin, exceeding browser storage limits,
or private/incognito browsing may prevent recovery. Enabling authenticated
cross-device cloud storage still requires correctly configured **OIDC
sign-in plus a TLS PostgreSQL service**. Do not upload confidential
government material into guest browser storage.

Offline CI exercises validated snapshots, new-session recovery, ordering,
rejected sensitive content and the actual JavaScript localStorage bridge
in a simulated browser environment. The final end-to-end check of a
Streamlit Cloud deployment requires a live browser with storage enabled.

## Temporary module visibility

**Communication Studio** is temporarily hidden from the ALBA navigation and
Chat Workspace's `Continue in` recommendations while its category rules
are being revised. This is controlled by `COMMUNICATION_STUDIO_VISIBLE` in
`alba_features.py`; set it to `True` when the module is ready to reopen.
The communication implementation and reference library are retained, and
**EU Communication & Reporting remains available** because it uses shared
communication back-end functions. Ordinary questions about social posts
can still be answered in the chat, but no link to the hidden page is offered.

## Phase 1 — Chat Workspace history management

The home Chat Workspace now shows one truthful storage state:

- **Saved to your account** only when a valid OIDC identity and a working
  external PostgreSQL database are both available.
- **Saved in this browser** only when the guest localStorage component
  acknowledges the exact current snapshot revision.
- **Saving in this browser** while a new guest revision is unconfirmed.
- **Not saved** if storage is disabled, blocked, full or cannot be verified.
  The app does not silently substitute session memory for an account database
  outage.

**Chat options** offers rename, portable JSON download and explicit
confirmation before permanent deletion. A compact **History backup** menu
downloads the complete bounded workspace (chats and Projects), restores one
conversation from a validated JSON backup, and restores a complete workspace
only when the guest workspace is empty (so existing data cannot be overwritten).
These tools store only screened public/synthetic content. The browser snapshot
uses the same v1 format and storage key as before.

The application awaits browser-save acknowledgment for new exchanges and
project moves as well as rename, deletion, creation and imports; account scope
transitions clear pending drafts to prevent cross-user leakage. Per-browser
storage remains limited; downloading a backup is prudent for important public
work. **This release does not activate cross-device history by itself.**
Production cloud persistence needs OIDC `[auth]` settings and
`ALBA_DATABASE_URL` with an authenticated TLS PostgreSQL service in the
Streamlit deployment secrets. No credentials belong in GitHub.

Testing: synthetic Streamlit AppTests and the database/backup layer run in
GitHub Actions. Live browser localStorage, authentication and external
PostgreSQL deployment must still be checked manually after deployment.
