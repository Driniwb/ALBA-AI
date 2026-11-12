# ALBA 2.0 – EUR-Lex / Cellar source integration

**Date:** 12 November 2026. **Status:** Official metadata and document-text retrieval proven; legal status verification not yet implemented.

## What is implemented

`eurlex_cellar.py` uses two official Publications Office services:

- **Cellar SPARQL:** `https://publications.europa.eu/webapi/rdf/sparql`. It finds the exact CELEX family of consolidated versions and documents registered as amending the base act through CDM relations.
- **Cellar REST:** `https://publications.europa.eu/resource/celex/{CELEX}?language=en`. It fetches actual text through an official document resolver and follows only permitted official content endpoints. When Cellar returns a legacy HTTP redirect on its own domain, the connector upgrades the URL to HTTPS **before** any subsequent request.

No EUR-Lex SOAP credentials are required for these read-only Cellar endpoints. The separate EUR-Lex SOAP **search** service requires registration.

The connector validates the CELEX, bounds response sizes, rejects unapproved redirect domains, restricts search queries to safe fixed templates, selects consolidated text for a given **as-of** date, checks CELEX and version date in the retrieved heading, and computes a digest of the normalized extracted text.

## Live evidence – 12 November 2026

The read-only pilot against official Cellar services for **Directive 2010/35/EU**, base CELEX `32010L0035`, `as_of=2026-11-12`, returned:

| Field | Official observation |
|---|---|
| Consolidated candidate | `02010L0035-20260530` |
| Consolidation date | 30 May 2026 |
| Amending act returned by the CDM relation | `32024L2749` |
| Official retrieved content stream | `https://publications.europa.eu/resource/cellar/176145a1-2d6a-11f1-906d-01aa75ed71a1.0008.02/DOC_1` |
| Text extracted | 68,649 characters |
| Heading observed | `02010L0035 — EN — 30.05.2026` |
| Corrigendum mentioned in the retrieved document | OJ L 90340 of 22 April 2025, concerning 2024/2749 |
| Retrieval result | `source_text_retrieved` |
| `version_verified` / `legal_status_verified` | **false / false** |

Source: [Official EUR-Lex consolidated version](https://eur-lex.europa.eu/eli/dir/2010/35/2026-05-30/eng). Technical evidence: [GitHub Actions live pilot](https://github.com/Driniwb/ALBA-AI/actions/runs/43226549554).

The first live query returned older, related directives together with the actual consolidation. We corrected this using an explicit base CELEX-family filter. The first text request also revealed a legacy official HTTP redirect; the client now upgrades it to HTTPS without making an HTTP request.

## What these results **do not** establish

A consolidated version is **not** itself the authentic act published in the EU Official Journal and has no independent legal effect. The SPARQL amending-act relation is evidence for further verification, not proof that all future-effective provisions, repeal acts, corrigenda, transitional rules or exceptions have been reconciled. An `as_of` date may differ from the consolidation date.

Accordingly, the connector deliberately reports `version_verified=False` and `legal_status_verified=False` even when a complete text is retrieved and its heading matches. Only the future legal verification layer may change those states, after documented checks against authentic Official Journal sources and actual application dates.

The property `metadata_complete` only means the returned query rows did not hit the configured 100-row cap; it is **not** a claim that every legally relevant relationship has been identified.

## Offline regression tests

`tests/test_eurlex_cellar.py` tests CELEX validation, bounded SPARQL search, version selection for a historical date, unrelated and malformed versions, content reading, source heading identity, official HTTP-to-HTTPS redirect upgrade, browser challenge rejection, third-party redirect rejection and the no-certification invariant. All of these tests use synthetic documents and mocks.

Use:

```bash
python -m unittest tests.test_eurlex_cellar -v
python eurlex_cellar.py 32010L0035 --as-of 2026-11-12
```

The second command makes live official-source requests; it is for manual checks and must not run on every CI test.

## Next acceptance gate

Before enabling an ALBA response such as **“current consolidated act verified”**, build a separate reconciliation step that:

1. Confirms base act status, repeal and replacement relations using official metadata and the authentic Official Journal.
2. Cross-checks all relevant amendments and corrigenda against the retrieved consolidation.
3. Checks applicability, entry-into-force, transitional and future-effective provisions against the user's requested legal date.
4. Anchors the cited article and paragraph to the exact retrieved text and preserves official links.
5. Returns **UNVERIFIED** when evidence is inaccessible, incomplete or inconsistent.

This integration is isolated in `develop/alba-v2`. Production branch `main` and the existing Streamlit application remain unchanged.
