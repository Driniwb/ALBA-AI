"""Offline regression tests for the EU legal status and version evidence gate."""
from datetime import date, timedelta
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from eurlex_verification import (
    CDM, _interpret_relations, _interpret_status,
    _textual_amendment_present, relationships_query, status_query, verify_eurlex,
)

BASE = "32010L0035"
CONSOL = "02010L0035-20260530"
TODAY = date.today()
HEADING = (
    "Consolidated TEXT: 32010L0035 — EN — 30.05.2026 "
    "02010L0035 — EN — 30.05.2026 — 001.001 "
    "This text is meant purely as a documentation tool and has no legal effect. "
    "DIRECTIVE 2010/35/EU OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL "
    "Amended by: ►M1 DIRECTIVE (EU) 2024/2749 OF THE EUROPEAN PARLIAMENT "
    "Corrected by: ►C1 Corrigendum OJ L 90340, 22.4.2025. "
    "Article 1 Scope. Article 2 Definitions."
)


def cellarevidence(*, text=True, amendments=None):
    return SimpleNamespace(
        selected_consolidation=CONSOL,
        consolidated_document_url="https://publications.europa.eu/resource/cellar/TEST/DOC_1",
        observed_amendments=["32024L2749"] if amendments is None else amendments,
        metadata_complete=True, content_retrieved=text,
        document_identity_observed=text,
    )


def sparql_rows(rows):
    class Response:
        status_code = 200
        headers = {"Content-Type": "application/sparql-results+json"}

        def __init__(self, rows):
            self._data = {"results": {"bindings": rows}}
            self.content = json.dumps(self._data).encode("utf-8")

        def json(self):
            return self._data

    return Response(rows)


def binding(**kwargs):
    return {key: {"type": "literal", "value": val}
            for key, val in kwargs.items()}


class Post:
    def __init__(self, status=True, *, end=None, entry="2010-07-20",
                 corrections=None, repeals=None, conflict=False):
        self.status = status
        self.end = end
        self.entry = entry
        self.corrections = corrections or []
        self.repeals = repeals or []
        self.conflict = conflict

    def __call__(self, url, *, data, headers, timeout, allow_redirects):
        assert url == "https://publications.europa.eu/webapi/rdf/sparql"
        query = data["query"]
        if "?value" in query:
            rows = []
            if self.status is not None:
                rows.append(binding(
                    predicate=CDM + "resource_legal_in-force",
                    value="true" if self.status else "false",
                ))
                if self.conflict:
                    rows.append(binding(
                        predicate=CDM + "resource_legal_in-force", value="false",
                    ))
            if self.entry:
                rows.append(binding(
                    predicate=CDM + "resource_legal_date_entry-into-force",
                    value=self.entry,
                ))
            if self.end:
                rows.append(binding(
                    predicate=CDM + "resource_legal_date_end-of-validity",
                    value=self.end,
                ))
            return sparql_rows(rows)
        items = []
        for celex in self.repeals:
            items.append(binding(
                predicate=CDM + "resource_legal_repeals_resource_legal",
                celex=celex,
            ))
        for celex in self.corrections:
            items.append(binding(
                predicate=CDM + "resource_legal_corrects_resource_legal",
                celex=celex,
            ))
        return sparql_rows(items)


class LegalVerificationTests(TestCase):
    def run_gate(self, *, post=None, content=HEADING, evidence=None, as_of=None):
        with patch("eurlex_verification.probe_eurlex",
                   return_value=(evidence or cellarevidence(), content)):
            return verify_eurlex(BASE, as_of=as_of or TODAY, post=post or Post())

    def test_queries_are_exact_finite_and_read_only(self):
        for query in (status_query(BASE), relationships_query(BASE)):
            self.assertIn("32010L0035", query)
            self.assertIn("LIMIT", query)
            self.assertNotIn("SERVICE", query)
            self.assertNotIn("INSERT", query)
        with self.assertRaises(ValueError):
            status_query("32010L0035 UNION ?x ?y ?z")

    def test_official_status_and_text_can_be_checked_without_certifying_law(self):
        r = self.run_gate()
        self.assertEqual(r.outcome, "source_and_status_metadata_checked")
        self.assertTrue(r.text_retrieved)
        self.assertTrue(r.text_identity_confirmed)
        self.assertTrue(r.metadata_status_checked)
        self.assertTrue(r.metadata_status_consistent)
        self.assertTrue(r.amendment_list_crosschecked)
        self.assertEqual(r.in_force_flag, True)
        self.assertEqual(r.entry_into_force, "2010-07-20")
        self.assertFalse(r.full_legal_verification)
        self.assertTrue(any("Corrigenda" in reason for reason in r.reasons))
        self.assertEqual(r.observed_corrigendum_citations,
                         ["OJ L 90340, 22.4.2025"])

    def test_missing_or_false_in_force_flag_prevents_status_claim(self):
        for value in (None, False):
            with self.subTest(flag=value):
                r = self.run_gate(post=Post(status=value))
                self.assertEqual(r.outcome, "metadata_unconfirmed")
                self.assertFalse(r.metadata_status_consistent)
                self.assertFalse(r.full_legal_verification)

    def test_future_entry_date_blocks_current_status(self):
        r = self.run_gate(post=Post(
            entry=(TODAY + timedelta(days=90)).isoformat()
        ))
        self.assertEqual(r.outcome, "metadata_unconfirmed")
        self.assertFalse(r.metadata_status_consistent)

    def test_end_of_validity_today_blocks_current_status(self):
        r = self.run_gate(post=Post(end=TODAY.isoformat()))
        self.assertEqual(r.outcome, "metadata_unconfirmed")
        self.assertFalse(r.metadata_status_consistent)

    def test_conflicting_status_values_fail_closed(self):
        r = self.run_gate(post=Post(conflict=True))
        self.assertEqual(r.outcome, "verification_blocked")
        self.assertFalse(r.metadata_status_checked)
        self.assertFalse(r.full_legal_verification)

    def test_amendment_missing_from_header_is_not_reconciled(self):
        r = self.run_gate(
            content=HEADING.replace("2024/2749", "2024/1234")
        )
        self.assertEqual(r.outcome, "amendment_reconciliation_incomplete")
        self.assertEqual(r.unmatched_amendment_citations, ["32024L2749"])
        self.assertFalse(r.amendment_list_crosschecked)

    def test_long_consolidation_header_does_not_create_false_missing_act(self):
        long_heading = HEADING.replace(
            "Amended by: ►M1 DIRECTIVE (EU) 2024/2749",
            "Amended by: " + "amendment preamble " * 500
            + "►M1 DIRECTIVE (EU) 2024/2749"
        )
        r = self.run_gate(content=long_heading)
        self.assertEqual(r.unmatched_amendment_citations, [])
        self.assertTrue(r.amendment_list_crosschecked)

    def test_repealing_act_is_flagged_for_review(self):
        r = self.run_gate(post=Post(repeals=["32025L0123"]))
        self.assertIn("32025L0123", r.observed_repealing_acts)
        self.assertTrue(any("repeal" in reason for reason in r.reasons))
        self.assertFalse(r.full_legal_verification)

    def test_corrigendum_is_observed_and_not_automatically_accepted(self):
        r = self.run_gate(
            post=Post(corrections=["32010L0035R(01)"])
        )
        self.assertEqual(r.observed_corrigenda, ["32010L0035R(01)"])
        self.assertFalse(r.full_legal_verification)

    def test_no_corrigendum_oj_reference_must_not_be_invented(self):
        text = HEADING.replace(
            "Corrected by: ►C1 Corrigendum OJ L 90340, 22.4.2025.",
            "Corrected by: unspecified correction."
        )
        r = self.run_gate(content=text)
        self.assertEqual(r.observed_corrigendum_citations, [])
        self.assertFalse(r.full_legal_verification)

    def test_historical_as_of_flag_is_not_approximated_by_current_status(self):
        r = self.run_gate(as_of=TODAY-timedelta(days=1))
        self.assertFalse(r.metadata_status_consistent)
        self.assertTrue(any("historical status" in s for s in r.reasons))

    def test_no_retrieved_text_blocks_confirmation(self):
        r = self.run_gate(
            evidence=cellarevidence(text=False), content=""
        )
        self.assertEqual(r.outcome, "verification_blocked")
        self.assertFalse(r.full_legal_verification)

    def test_bad_relation_metadata_is_rejected(self):
        rows = [binding(
            predicate=CDM + "resource_legal_repeals_resource_legal",
            celex="NOT_A_CELEX",
        )]
        with self.assertRaises(ValueError):
            _interpret_relations(rows)

    def test_invalid_in_force_value_is_rejected(self):
        rows = [binding(
            predicate=CDM + "resource_legal_in-force", value="maybe",
        )]
        with self.assertRaises(ValueError):
            _interpret_status(rows)

    def test_amendment_match_only_in_header(self):
        self.assertTrue(_textual_amendment_present(HEADING, "32024L2749"))
        self.assertFalse(_textual_amendment_present(
            "No relevant amendment." + "x"*5200 + "2024/2749",
            "32024L2749"
        ))


if __name__ == "__main__":
    import unittest
    unittest.main()
