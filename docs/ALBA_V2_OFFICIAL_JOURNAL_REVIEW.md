# ALBA 2.0 – Official Journal amendment and corrigendum review

**Date:** 12 November 2026  
**Branch:** `develop/alba-v2`  
**Status:** Official Journal amendment text and source metadata retrieved; all corrigenda discovered; complete legal verification **not yet achieved**.

## Implemented

`eurlex_oj_review.py` provides a read-only source-evidence workflow:

1. Retrieve the **authentic Official Journal amending act** from the
   Publications Office Cellar text resolver and validate its heading.
2. Check that its operative clauses actually refer to amending the
   requested base act (not merely a title or recital mentioning it).
3. Read the original amending act's in-force metadata and entry-into-force
   date. **Distinguish** these from the national transposition deadline and
   national-measures application date stated in the OJ text.
4. Discover all available corrigendum CELEX identifiers using the official
   `resource_legal_corrects_resource_legal` relation for the **amending
   act**, not only for the base directive.
5. Read the base directive's dated consolidated version and locate an
   article/paragraph in its text. Avoid confusing article citations with
   article headings or paragraph numbering.
6. Mark separately conditional emergency-mode application, incomplete
   corrigendum-text review and other legal-effect uncertainty.

The output contains source URL, extracted-text digest, CELEX, observed dates,
corrigenda identifiers, provision fragment and unresolved checks. It never
sets `complete_legal_verification=true` at this stage.

## Real official-source pilot

**Target:** Directive 2010/35/EU (CELEX `32010L0035`)  
**Amending act:** Directive (EU) 2024/2749 (`32024L2749`)  
**Requested date:** 12 November 2026  
**Provision:** Article 33c(9)

| Check | Result |
|---|---|
| Authentic OJ amending-act heading | Confirmed |
| Operative amendment to Directive 2010/35/EU | Found |
| Amending act entered into force | **28 November 2024** |
| Deadline to adopt and publish national transposition measures | **29 May 2026**, per Article 11(1) |
| National measures to apply from | **30 May 2026**, per Article 11(2) |
| Corrigendum records returned by official Cellar CDM | **R(01), R(02), R(03), R(04)** |
| Dated consolidation | `02010L0035-20260530` |
| Article 33c(9) in consolidated text | Found; refers to **Article 12** |
| Emergency applicability conditions | Found in Article 33a |
| Full legal verification | **false** |

Technical proof: [Live GitHub Actions test](https://github.com/Driniwb/ALBA-AI/actions/runs/43251849093).

### Authentic amendment and corrigendum

- [2024/2749 — authentic Official Journal act](https://eur-lex.europa.eu/eli/dir/2024/2749/oj/eng)
- [2010/35/EU — official 30 May 2026 consolidation](https://eur-lex.europa.eu/eli/dir/2010/35/2026-05-30/eng)
- [R(01) — corrigendum, OJ L 2025/90340 of 22 April 2025](https://eur-lex.europa.eu/eli/dir/2024/2749/corrigendum/2025-04-22/oj/eng)

The **public EUR-Lex page** for corrigendum R(01) states that its Article
33c(9) reference is corrected from Article **18** to Article **12**.
The consolidated text also contains Article **12** in that provision.
This correspondence was confirmed through separate public-source inspection,
but the ALBA program itself could not retrieve the authentic corrigendum
text via the tested Cellar `resource/celex` resolver: it returned HTTP
**404**, while the EUR-Lex ELI page returned HTTP **202** to the GitHub
runner. **The backend therefore does not claim to have independently
verified the correction's authoritative text.**

R(02) is associated with a correction concerning Article 38d(5) of Directive
2014/34/EU; R(03) and R(04) require separate assessment of language and
scope. Discovery of an amendment's corrigendum does **not** imply that
the corrigendum changes Directive 2010/35/EU or the requested English
provision.

### Important applicability distinction

A national-measures application date is not a statement that every emergency
provision is applicable unconditionally. Article **33a** of Directive
2010/35/EU links the operation of emergency procedures to a Commission
implementing act, designation of crisis-relevant goods and an activated
internal-market emergency mode, subject to particular exceptions. ALBA
must check these conditions for any requested legal date before deciding
whether a specific emergency procedure can be used.

## Verification states and boundaries

- `oj_and_change_metadata_checked`: authentic OJ amending act read,
  operative clause found, corrigendum **identifiers** discovered, relevant
  consolidated article located. **Not legal certification.**
- `oj_source_unconfirmed`: OJ heading missing or document inaccessible.
- `operative_amendment_unconfirmed`: no operative clause amending target.
- `change_history_unconfirmed`: corrigendum relation query unavailable.
- `consolidated_text_unconfirmed`: no dated consolidated text established.
- `provision_unconfirmed`: requested article/paragraph cannot be anchored.
- `corrigendum_texts_verified=false`: the original corrigendum text is
  not programmatically available/verified for all relevant corrections.
- `complete_legal_verification=false`: always enforced at this stage.

Tests: `tests/test_eurlex_oj_review.py` (offline) exercise the gate with
synthetic OJ and consolidated texts, including missing evidence, false
article-header matches, incorrect dates and multiple corrigenda.

## Next work

1. Resolve access to authentic **corrigendum OJ texts** through an officially
   supported format/API; do not bypass access restrictions.
2. Determine corrigendum **language scope** and which exact base-act
   provision each correction affects, before adding it to a law-in-force
   assertion.
3. Map commencement, transitional and activation conditions at
   article/paragraph level; retrieve relevant implementing measures and
   check the date-specific state.
4. Only then permit a **provision-specific verification** result.
   No generic green label for an entire act should be inferred from a
   matching consolidation and metadata alone.
5. Expose source statuses and direct links in the future ALBA 2.0 sources
   panel; the current live application is untouched.

**Production `main` is unchanged.**
