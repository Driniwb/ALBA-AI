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
