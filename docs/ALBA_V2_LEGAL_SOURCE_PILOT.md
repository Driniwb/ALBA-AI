# ALBA 2.0 — Legal source verification pilot

Date: 2026-11-12. This is a **read-only connectivity and metadata
pilot**, not a verified consolidated-law engine.

## Phase 1 implemented

The input manifest, `tests/fixtures/legal_source_pilot_20.json`, defines
10 candidate Albanian ELI paths and 10 candidate EU CELEX records. Their
identities and URL reachability still require a live check. These inputs are
**not a list of verified or currently applicable laws**.

The module `legal_sources_probe.py` observes visible official-document
metadata while deliberately keeping `version_verified` and
`status_verified` set to `false`. It never invents the effective legal text.

For QBZ the pilot now extracts **two different evidence streams**:

1. **Versions of the updated document**, including the visible numbered
   version and its "në fuqi nga" date. A candidate version is selected for
   a requested historical date, if observed.
2. **Ndërvarësia → Ndryshuar nga**, including the declared count of
   amending acts and any individually observed identifiers and dates.
   It does not treat the separate "Bazë ligjore për" relationships as
   amending acts.

These streams are **not interchangeable**. A count of amending acts need
not equal the count of published updated versions. A later amendment,
repeal, corrigendum or delayed commencement can invalidate a simplistic
"latest version" inference.

## Run a connectivity probe

From a network-enabled environment, with the project's dependencies:

    python legal_sources_probe.py --manifest tests/fixtures/legal_source_pilot_20.json --output probe-results.json

Outcomes: `identity_candidate`, `document_unconfirmed`,
`access_challenge`, `redirect_blocked`, `http_error`,
`network_error`, `unsupported_format`, `too_large`.
A successful HTTP response is **not** a legal verification.

The output includes source URL, retrieval timestamp, observed version dates
and observed amending-act references where available. Because a public
website may require dynamic rendering, absence of visible data does not
prove that the act has no changes.

## Phase 2: requirements before citing "current in force"

For **QBZ**, the production connector must verify:
- correct ELI, type, number, date and title;
- legal status and effective dates;
- the actual text of the selected updated version (PDF/DOCX or equivalent);
- all relevant amending and repealing acts in "Ndryshuar nga" and other
  applicable changes, with effect on the selected as-of date;
- whether the updated text incorporates the changes that are already effective;
- the exact article/paragraph quoted, with a direct official source link.

For **EUR-Lex**, the connector must verify:
- CELEX/ELI identity;
- original act status;
- latest consolidation applicable at the requested date;
- amendment/corrigendum history and changes not yet consolidated;
- future effective or applicable provisions;
- exact article/paragraph and links to the consolidated text and official
  amending acts. Consolidations are documentary tools, not a substitute
  for authoritative acts in the Official Journal.

If any required check is impossible, ALBA must say **not verified** rather
than present the document as the current legally applicable act.

## Technical notes and next tests

- Official source URLs are restricted by host, scheme and path.
- Redirects to unrelated hosts are rejected.
- Tests run offline against synthetic, public-looking metadata.
- No production application files or `main` branch are modified.
- Phase 1 does **not** establish live connectivity for all 20 records
  or legally confirm any consolidated version.
- The next step is a jurisdiction-specific connector with robust content
  retrieval, canonical IDs and source-provenance records.


## Phase 2 implementation — 12 November 2026

The module `legal_source_documents.py` now performs **read-only parsing and
actual PDF text extraction** from an explicitly mapped QBZ Alfresco WebDAV
document repository, when the repository provides a usable directory listing.
The call `retrieve_qbz_document(eli, as_of=...)` returns:

- the chosen original or dated consolidation repository folder;
- the direct QBZ PDF URL, if discovered;
- SHA-256 of retrieved PDF bytes and optional equality check against a
  separately supplied official SHA-256;
- PDF page count, extracted text length and a source-text string;
- a cautious document-heading identity check against the ELI;
- legal version and legal status **always marked unverified**.

The new regression suite `tests/test_legal_source_documents.py` covers:
historic repository cut-offs, source heading checks, SHA-256 mismatch,
scanned/unreadable documents, multiple PDF ambiguity, and restricted official
hosts. All tests use locally generated **synthetic** PDF documents. They
prove the module behavior, not access to the live QBZ catalogue.

### Live access diagnostics (12 November 2026)

A one-time read-only GitHub Actions runner test targeted the official QBZ
repository path for VKM no. 325/2023:

- Directory GET: HTTP **200**, text/html, **1,521 bytes**, **zero hrefs**
  and no version folders in returned content.
- WebDAV PROPFIND: HTTP **200**, HTML, **758 bytes**, no multistatus
  XML or directory entries.
- Experimental public Alfresco AFTS search POST: HTTP **405**.
- Consequently the PDF selection/reading operation returned
  `read_or_validation_failed`; **no document text and no legal version
  was confirmed**. This was an access-path failure, not a conclusion about
  the legal act.

CI run evidence: https://github.com/Driniwb/ALBA-AI/actions/runs/43223150994

An external search index shows that QBZ has version folders in its public
repository, but an indexed page is not equivalent to a functioning
programmatic listing for our application. The approach MUST NOT bypass
access restrictions or substitute a cached summary for official document
retrieval. We need a stable officially permitted access mechanism (or
explicitly supplied official PDFs with provenance) before this connector
can be enabled for users.

**Important temporal detail:** QBZ's repository cut-off folder (e.g.
`cons-2026-07-15`) may differ from its legal effective-date timeline
(e.g. `Versioni 14, në fuqi nga 09/07/2026` for VKM 325/2023).
Folder labels cannot substitute for the official date of legal effect.

### Phase 3 acceptance gate

Do not enable a verified/current-law badge until an official connector
can obtain and reconcile the act's identity, applicable full text,
published amendment list, repeal/status and effective dates, with
direct official citations and explicit provenance. Unavailable evidence
must result in an unverified answer, not an inferred conclusion.
