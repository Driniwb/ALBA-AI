"""Offline tests for authentic OJ amendment review and unverified corrigenda."""
from datetime import date, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eurlex_oj_review import (
    _oj_identity, _mentions_amended_base, _transposition_dates,
    _article_text, review_oj_amendment,
)
from eurlex_verification import CDM

BASE = "32010L0035"
AMEND = "32024L2749"
CONSOL = "02010L0035-20260530"
OJ = (
    "L_202402749EN.000101.fmx.xml "
    "Official Journal of the European Union EN L series 2024/2749 8.11.2024 "
    "DIRECTIVE (EU) 2024/2749 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL "
    "of 9 October 2024 amending Directives 2000/14/EC, 2006/42/EC, 2010/35/EU "
    "Article 3 In Directive 2010/35/EU, the following amendments are made: "
    "Article 11 Transposition 1. By 29 May 2026 Member States shall adopt and "
    "publish the measures necessary to comply with this Directive. "
    "2. They shall apply those measures from 30 May 2026. "
    "Article 12 Entry into force This Directive shall enter into force "
    "on the twentieth day following that of publication in the Official Journal."
)
CONS = (
    "Consolidated TEXT: 32010L0035 — EN — 30.05.2026 "
    "Article 33a Application of emergency procedures "
    "1. Member States shall ensure that measures taken to transpose "
    "Articles 33b, 33c and 33d of this Directive apply only if the Commission "
    "has adopted an implementing act. "
    "2. They shall apply only to crisis-relevant goods. "
    "3. The measures apply only during the internal market emergency mode. "
    "Article 33b Prioritisation 1. Introductory duties. "
    "Article 33c Derogation from conformity assessment "
    "1. By way of derogation from Article 12, authorisations may be granted. "
    "2. A Member State shall notify the Commission. "
    "9. The use of the authorisation procedure shall not affect "
    "the conformity assessment procedures laid down in Article 12. "
    "Article 33d Prioritisation of market surveillance activities "
    "1. Authorities shall prioritise inspections."
)


def row(**fields):
    return {key: {"type": "literal", "value": value}
            for key, value in fields.items()}


def mock_rows(query, *, post, row_limit):
    if "?value" in query:
        return [
            row(predicate=CDM + "resource_legal_in-force", value="true"),
            row(predicate=CDM + "resource_legal_date_entry-into-force",
                value="2024-11-28"),
        ]
    return [
        row(predicate=CDM + "resource_legal_corrects_resource_legal",
            celex=f"32024L2749R({n:02d})")
        for n in range(1, 5)
    ]


class OjReviewTests(unittest.TestCase):
    def run_review(self, *, amendment_text=OJ, base_text=CONS,
                   corrigenda=True, article="33c", paragraph="9",
                   as_of=None, retrieval_error=False):
        def download(celex, *, get):
            if retrieval_error:
                raise ValueError("Official OJ server returned 404")
            self.assertEqual(celex, AMEND)
            return ("https://publications.europa.eu/resource/cellar/TEST/DOC_1",
                    amendment_text)

        def rows(query, *, post, row_limit):
            if not corrigenda and "?celex" in query:
                return []
            return mock_rows(query, post=post, row_limit=row_limit)

        evidence = SimpleNamespace(
            selected_consolidation=CONSOL,
            content_retrieved=True,
            document_identity_observed=True,
        )
        with (
            patch("eurlex_oj_review._download_text", side_effect=download),
            patch("eurlex_oj_review._rows", side_effect=rows),
            patch("eurlex_oj_review.probe_eurlex", return_value=(evidence, base_text)),
        ):
            return review_oj_amendment(
                BASE, AMEND, as_of=as_of or date.today(),
                post=object(), get=object(), provision_article=article,
                provision_paragraph=paragraph,
            )

    def test_amending_act_identity_uses_oj_heading(self):
        self.assertTrue(_oj_identity(OJ, AMEND))
        self.assertFalse(_oj_identity(OJ.replace("2024/2749", "2024/9999"), AMEND))
        self.assertFalse(_oj_identity("A media report summarised DIRECTIVE (EU) 2024/2749", AMEND))

    def test_transposition_dates_are_distinct_from_entry_into_force(self):
        self.assertEqual(_transposition_dates(OJ), ("2026-05-29", "2026-05-30"))
        self.assertEqual(_transposition_dates(OJ.replace("Article 11 Transposition", "Section 11")),
                         (None, None))

    def test_retrieves_oj_amending_text_and_discovers_four_corrigenda(self):
        report = self.run_review()
        self.assertEqual(report.outcome, "oj_and_change_metadata_checked")
        self.assertTrue(report.oj_heading_identified)
        self.assertTrue(report.base_mentioned_in_amending_text)
        self.assertEqual(report.amending_act_entry_into_force, "2024-11-28")
        self.assertEqual(report.national_transposition_deadline, "2026-05-29")
        self.assertEqual(report.national_measures_application_date, "2026-05-30")
        self.assertEqual(report.observed_corrigenda_celex, [
            "32024L2749R(01)", "32024L2749R(02)",
            "32024L2749R(03)", "32024L2749R(04)",
        ])
        self.assertTrue(report.corrigendum_discovery_checked)
        self.assertFalse(report.corrigendum_texts_verified)
        self.assertFalse(report.complete_legal_verification)
        self.assertIn("Article 12", report.provision_text)
        self.assertTrue(report.conditional_application_identified)

    def test_article_extraction_does_not_start_from_incidental_reference(self):
        text = CONS.replace(
            "Article 33c Derogation",
            "Article 33c(7) must remain applicable. Article 33c Derogation",
        )
        extracted = _article_text(text, "33c", "9")
        self.assertIn("Article 12", extracted)
        self.assertNotIn("authorisations may be granted", extracted)

    def test_no_corrigenda_returned_does_not_mean_no_corrigenda(self):
        report = self.run_review(corrigenda=False)
        self.assertEqual(report.observed_corrigenda_celex, [])
        self.assertFalse(report.corrigendum_texts_verified)
        self.assertTrue(any("does not establish absence" in reason
                            for reason in report.unresolved))

    def test_oj_failure_stays_unconfirmed(self):
        report = self.run_review(retrieval_error=True)
        self.assertEqual(report.outcome, "oj_source_unconfirmed")
        self.assertFalse(report.oj_heading_identified)
        self.assertFalse(report.complete_legal_verification)

    def test_wrong_oj_does_not_confirm_identity(self):
        report = self.run_review(
            amendment_text=OJ.replace(
                "DIRECTIVE (EU) 2024/2749", "DIRECTIVE (EU) 2024/9999"
            )
        )
        self.assertFalse(report.oj_heading_identified)
        self.assertEqual(report.outcome, "oj_source_unconfirmed")

    def test_missing_corrected_provision_blocks_article_claim(self):
        report = self.run_review(base_text=CONS.replace(
            "9. The use of the authorisation procedure shall not affect "
            "the conformity assessment procedures laid down in Article 12. ", ""
        ))
        self.assertIsNone(report.provision_text)
        self.assertFalse(report.complete_legal_verification)
        self.assertTrue(any("could not be anchored" in x for x in report.unresolved))

    def test_unknown_operative_amendment_clause_is_not_assumed(self):
        report = self.run_review(
            amendment_text=OJ.replace(
                "Article 3 In Directive 2010/35/EU,",
                "Article 3 The legal instrument",
            )
        )
        self.assertFalse(report.base_mentioned_in_amending_text)
        self.assertFalse(report.complete_legal_verification)

    def test_future_transposition_application_is_not_confused_with_entry(self):
        self.assertNotEqual("2024-11-28", "2026-05-30")
        report = self.run_review(as_of=date(2025, 12, 1))
        self.assertEqual(report.national_measures_application_date, "2026-05-30")
        self.assertFalse(report.complete_legal_verification)

    def test_missing_provision_is_not_fabricated(self):
        report = self.run_review(article="99x", paragraph="9")
        self.assertIsNone(report.provision_text)
        self.assertFalse(report.complete_legal_verification)

    def test_reject_malicious_celex_and_provision_identifier(self):
        with self.assertRaises(ValueError):
            _oj_identity(OJ, "32024L2749);DROP")
        with self.assertRaises(ValueError):
            _article_text(CONS, "33c.*", "9")


if __name__ == "__main__":
    unittest.main()
