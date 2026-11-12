# ALBA 2.0 — EUR-Lex Legal Verification Gate

Date: 12 November 2026  
Branch: `develop/alba-v2`  
Status: **Official document + status-metadata evidence implemented; full legal-effect certification deliberately withheld.**

## Purpose

The separate module `eurlex_verification.py` extends `eurlex_cellar.py`. It checks:

1. Exact CELEX family, retrieved consolidated text, its edition date and official Cellar source.
2. Base act's **in-force flag**, entry-into-force date and end-of-validity date using official Cellar CDM metadata.
3. Documented amendment relationships, preliminary matching against the list of amendments visible in the consolidated text heading.
4. Documented repeal and correction relations, and identifiable Official Journal corrigendum citations from the text heading.
5. A **fail-closed** result when metadata is unavailable, contradictory, incomplete or inconsistent.

The output preserves exact sources and date. Its boolean `full_legal_verification`
remains **false** because article-specific applicability, transitional clauses,
late changes, language-specific corrigenda and legally authentic Official
Journal acts have **not** yet been completely reconciled.

This is intentional: an official consolidation is a **documentation tool**,
not itself legally authentic text.

## Official sources

- [Cellar SPARQL endpoint](https://publications.europa.eu/webapi/rdf/sparql)
- [Cellar documentation and CDM metadata](https://op.europa.eu/en/web/cellar/cellar-data/metadata/knowledge-graph)
- [EUR-Lex consolidated texts and limitations](https://eur-lex.europa.eu/collection/eu-law/consleg.html?locale=en)

No commercial API credentials were necessary for this read-only implementation.

## Live checks (as of 12 November 2026)

The isolated GitHub Actions test [run 43248803538](https://github.com/Driniwb/ALBA-AI/actions/runs/43248803538) checked:

| Base directive | Observed consolidation | Cellar in-force flag | Amendment relations | Outcome at first run |
|---|---|---|---|---|
| 2008/68/EC (32008L0068) | 02008L0068-20260512 | true | 27 | Five amendment references were not matched in an initial short extracted HTML header; **this is NOT evidence of omitted legal amendments** |
| 2010/35/EU (32010L0035) | 02010L0035-20260530 | true | 1 | Text identity and status metadata consistent |
| (EU) 2016/798 (32016L0798) | 02016L0798-20201023 | true | 2 | Text identity and status metadata consistent |

The test exposed an important shortcoming in strict text-only matching:
some older acts appear as amending measures in the official amendment table,
but not always with their full act number in the extracted HTML. The code
now searches the *whole front-matter amendment table*, while treating any
unmatched item as **a reconciliation task** rather than proof of a legal
inconsistency.

The text of 2010/35/EU refers to a corrigendum in **OJ L 90340 of 22 April
2025**. The text of (EU) 2016/798 refers to corrigenda in **OJ L 059 of
7 March 2017** and **OJ L 317 of 9 December 2019**. These are reported as
observed citation strings, **not yet confirmed as language-relevant changes
to the requested provision**.

The official metadata for 2010/35/EU returned entry into force
**2010-07-20**, end of validity **9999-12-31** (Cellar open-ended
sentinel, not an actual expiry date), and an in-force flag of `true`
on the query date. This is a metadata observation, **not a blanket
declaration that all provisions apply without transitional conditions**.

## Interpreting the response

| Field/outcome | Meaning |
|---|---|
| `source_and_status_metadata_checked` | Official text identity confirmed and status metadata consistent with the current date; complete legal verification **not** established |
| `metadata_unconfirmed` | Missing/negative/temporally conflicting metadata, or a historical-date query that cannot be inferred from the present-day in-force flag |
| `amendment_reconciliation_incomplete` | A citation could not be matched in the extracted consolidation heading; potentially due to missing numbers in HTML formatting, not necessarily missing legal changes |
| `verification_blocked` | Required source/metadata is unavailable, malformed or contradictory |
| `full_legal_verification: false` | ALBA must not label the source as fully legally verified |

No such flag means that the exact legal effect of an individual article has
been established. For a historical `as_of` date the **present-day in-force
flag is not used** as a substitute for historical status.

## How to run

The offline regression suite is included in the default workflow:

```bash
python -m unittest tests.test_eurlex_verification -v
```

Manual (read-only, live Cellar) check:

```bash
python eurlex_verification.py 32010L0035 --as-of 2026-11-12
```

Live calls depend on official server accessibility. Default GitHub CI
should use synthetic regression tests and **not** rely on external availability.

## Remaining work before production/legal certification

1. Verify each applicable amendment and repeal against the **authentic
   Official Journal** act and its individual operative dates.
2. Resolve corrected-language scope and all relevant corrigenda, including
   cases that do not appear in a simple CDM relation query.
3. Check the act's and each provision's entry-into-force,
   delayed applicability, transitional and exception rules.
4. Anchor exact article/paragraph references to the retrieved and versioned
   text, with the official version URL and retrieval date.
5. Handle unamended acts by retrieving the authentic original text, rather
   than treating absence of consolidations as proof the act is unavailable.
6. Integrate structured verification findings into ALBA Chat without
   converting an unverified finding into a fabricated legal assertion.

Production branch `main` and existing UI remain unchanged.
