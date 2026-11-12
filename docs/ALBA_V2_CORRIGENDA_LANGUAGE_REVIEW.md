# ALBA 2.0 – EUR-Lex Authentic Corrigenda and Language Scope (Step 6)

**Date:** 12 November 2026  
**Code:** `eurlex_corrigenda.py`  
**Branch:** `develop/alba-v2`  
**Scope:** English-text correction of Article 33c(9) of Directive 2010/35/EU.

## Implemented

The official Publications Office Cellar SPARQL endpoint is queried using
the corrigendum's **exact CELEX identifier**, e.g.
`32024L2749R(01)`. The identifier is resolved to the unique **Cellar work
URI**, which is then used to request the English XHTML manifestation.

The earlier `/resource/celex/32024L2749R(01)` route returned HTTP 404 in
the GitHub runner. Using the authoritative work URI instead succeeds without
bypassing authentication, anti-bot measures or source restrictions.

A second official SPARQL query checks the **expression languages** through:

`cdm:expression_belongs_to_work` and `cdm:expression_uses_language`.

This avoids treating a Latvian-only or Swedish-only corrigendum as a
missing English source.

The system also:

- validates source document identity and EN-language heading;
- records the authentic stream URL, publication date and normalized-text hash;
- identifies the directive, article and paragraph expressly targeted in
  the text of a correction, if this is stated unambiguously;
- extracts the authentic `for:` / `read:` pair (without silently
  inventing missing text);
- compares corrected text against the selected dated consolidation;
- keeps source-text consistency separate from **legal applicability**.

All of this is read only. No changes are made to any official publication.

## Live evidence – 12 November 2026

**Base:** Directive 2010/35/EU, CELEX `32010L0035`  
**Amendment:** Directive (EU) 2024/2749, CELEX `32024L2749`  
**Provision:** Article 33c(9)  
**Consolidation:** `02010L0035-20260530`  
**Requested date:** 12 November 2026  
**Requested language:** English (EN).

| Corrigendum | Official language scope | Result for Article 33c(9), EN |
|---|---|---|
| `32024L2749R(01)` | English among published expressions | Text retrieved; published 22 April 2025; reference corrected from Article 18 to Article 12; exact corrected passage matches consolidated Article 33c(9) |
| `32024L2749R(02)` | English among published expressions | Text retrieved; published 17 September 2025; correction concerns Article 38d(5) of Directive 2014/34/EU, not the requested provision |
| `32024L2749R(03)` | Latvian (`LAV`) only | Official language metadata excludes English; no English document fetch required |
| `32024L2749R(04)` | Swedish (`SWE`) only | Official language metadata excludes English; no English document fetch required |

**Result:** `corrigenda_inspected`; all four were classified for the
requested English provision, none remains unresolved **within this scoped
corrigendum review**, and the exact R(01) corrected passage was found in
the dated consolidation.

**Important:** `all_corrigendum_texts_retrieved=false` is intentionally
honest: the Latvian-only and Swedish-only texts were not downloaded.
`english_scope_complete=true` means that official metadata established
they are **outside the English review**.

`full_legal_verification=false` remains mandatory. The result does not
certify whether the emergency measures are activated or all provisions
are applicable at the requested date.

### Official sources

- [R(01), 22 April 2025, EUR-Lex](https://eur-lex.europa.eu/eli/dir/2024/2749/corrigendum/2025-04-22/oj/eng)
- [R(02), 17 September 2025, EUR-Lex](https://eur-lex.europa.eu/eli/dir/2024/2749/corrigendum/2025-09-17/oj/eng)
- [R(03), Latvian-only, EUR-Lex](https://eur-lex.europa.eu/legal-content/LV/ALL/?uri=CELEX%3A32024L2749R%2803%29)
- [R(04), Swedish-only, Publications Office](https://op.europa.eu/sv/publication-detail/-/publication/13dbc034-c76c-11f1-a77b-01aa75ed71a1/language-sv)
- [Selected 30 May 2026 consolidated text](https://eur-lex.europa.eu/eli/dir/2010/35/2026-05-30/eng)

**Technical evidence:** GitHub Actions live-source check
[43255024571](https://github.com/Driniwb/ALBA-AI/actions/runs/43255024571).
Earlier work-ID and XHTML checks:
[43252815753](https://github.com/Driniwb/ALBA-AI/actions/runs/43252815753),
[43253076903](https://github.com/Driniwb/ALBA-AI/actions/runs/43253076903).
The WEMI language check uses the Publications Office's documented inverse
expression-belongs-to-work relationship.

## Verification and safety boundaries

1. No third-party URLs or unexpected redirects are followed. A legacy
   HTTP redirect is upgraded to HTTPS for the **same official Cellar work**
   before any content request.
2. An empty/ambiguous SPARQL work result is an error, not permission to
   infer or invent the corrigendum's content.
3. An empty/failed language query does not mean English is excluded:
   the result is **unknown** until a source is confirmed.
4. If the requested legal date precedes publication, the correction must
   not be applied retrospectively without further legal justification.
5. Target and language are checked at the **specific article/paragraph
   and expression level**. Merely being a corrigendum to the same amending
   directive is not enough.
6. Text consistency does not establish full legal effect. Emergency
   activation, future-effective provisions, other applicable amendments
   and transitional rules require separate verification.
7. The current extraction handles a common single-correction English OJ
   `for/read` format. Multi-correction documents, complex tables or
   different source language layouts require additional parsing or human
   review before confirmation.

## Tests

Offline regression tests: `tests/test_eurlex_corrigenda.py`. They cover:

- Validated source/CELEX, unique official work resolution;
- Official HTTPS-only content stream and redirect restrictions;
- Authentic English identity;
- Exact correction `for/read` matching;
- Unrelated directives, unknown target or future publication;
- Non-English-only documents (Latvian/Swedish) without false 404 claims;
- Ambiguous/empty language data and strict non-certification.

**Next step:** provision-level temporal applicability review, especially
Article 33a emergency-mode activation conditions, related Commission
implementing acts and explicit source-linked evidence for a requested date.

ALBA `main` remains untouched. The new connector is still not wired into
the production Chat Assistant.
