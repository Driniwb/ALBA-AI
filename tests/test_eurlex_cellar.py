"""Offline Cellar integration tests; no external service or legal certification."""
from datetime import date
import json
import unittest

from eurlex_cellar import (
    amendments_query, consolidation_query, probe_eurlex, select_consolidation,
)

CELEX = "32010L0035"
CONSOL_1 = "02010L0035-20241001"
CONSOL_2 = "02010L0035-20260530"


class Response:
    def __init__(self, body, status=200, kind=None, location=None):
        self.status_code = status
        self.content = body.encode("utf-8")
        self.text = body
        self.headers = {"Content-Type": kind or "application/sparql-results+json"}
        if location:
            self.headers["Location"] = location

    def json(self):
        return json.loads(self.text)


def bindings(*values):
    data = {
        "head": {"vars": ["celex"]},
        "results": {"bindings": [
            {"celex": {"type": "literal", "value": value}} for value in values
        ]},
    }
    return Response(json.dumps(data))


class FakePost:
    def __init__(self, versions=None, amendments=None):
        self.versions = versions if versions is not None else [CONSOL_1, CONSOL_2]
        self.amendments = amendments if amendments is not None else ["32024L2749"]
        self.queries = []

    def __call__(self, url, *, data, timeout, allow_redirects, headers):
        self.queries.append((url, data["query"]))
        assert not allow_redirects
        assert "publications.europa.eu" in url
        if "act_consolidated_" in data["query"]:
            return bindings(*self.versions)
        return bindings(*self.amendments)


class FakeGet:
    def __init__(self, *, challenge=False, mismatched=False, redirect=False, legacy_redirect=False):
        self.urls = []
        self.challenge = challenge
        self.mismatched = mismatched
        self.redirect = redirect
        self.legacy_redirect = legacy_redirect

    def __call__(self, url, *, timeout, allow_redirects, headers):
        self.urls.append(url)
        assert not allow_redirects
        if self.redirect:
            return Response("", status=302,
                            location="https://attacker.example/spoof")
        if self.legacy_redirect and len(self.urls) == 1:
            return Response("", status=302, location=(
                "http://publications.europa.eu/resource/cellar/"
                "176145a1-2d6a-11f1-906d-01aa75ed71a1.0008.02/DOC_1"
            ))
        body = (
            "verify that you're not a robot"
            if self.challenge else
            f"<html><body><h1>{'Wrong' if self.mismatched else CONSOL_2}</h1>"
            "<p>Directive on transportable pressure equipment.</p></body></html>"
        )
        return Response(body, kind="text/html")


class EurlexCellarTests(unittest.TestCase):
    def test_invalid_celex_never_reaches_external_service(self):
        for value in ("", "32010L0035' UNION {}", "02010L0035-20260530",
                      "32010L0035/../../etc", "62011CJ0001"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    consolidation_query(value)

    def test_bounded_read_only_queries_and_source_predicates(self):
        for query in (consolidation_query(CELEX), amendments_query(CELEX)):
            self.assertIn("LIMIT 100", query)
            self.assertIn("resource_legal_id_celex", query)
            self.assertNotIn("SERVICE", query)
            self.assertNotIn("DELETE", query)
        self.assertIn("act_consolidated_based_on_resource_legal",
                      consolidation_query(CELEX))
        self.assertIn('STRSTARTS(STR(?celex), "02010L0035-")',
                      consolidation_query(CELEX))
        self.assertIn("resource_legal_amends_resource_legal",
                      amendments_query(CELEX))

    def test_as_of_keeps_old_version_and_never_future(self):
        chosen, all_versions = select_consolidation(
            CELEX, [CONSOL_1, CONSOL_2], date(2025, 1, 1)
        )
        self.assertEqual(chosen, CONSOL_1)
        self.assertEqual(len(all_versions), 2)
        earlier, _ = select_consolidation(
            CELEX, [CONSOL_1, CONSOL_2], date(2020, 1, 1)
        )
        self.assertIsNone(earlier)

    def test_reject_unrelated_or_malformed_consolidation(self):
        for value in ("02008L0068-20260530", "02010L0035-20261340",
                      "X2010L0035-20260530"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    select_consolidation(CELEX, [value], date(2026, 11, 12))

    def test_retrieve_realistic_consolidated_html_but_never_certify_law(self):
        post, get = FakePost(), FakeGet()
        evidence, text = probe_eurlex(
            CELEX, as_of=date(2026, 11, 12), post=post, get=get
        )
        self.assertEqual(evidence.selected_consolidation, CONSOL_2)
        self.assertEqual(evidence.outcome, "source_text_retrieved")
        self.assertTrue(evidence.document_identity_observed)
        self.assertTrue(evidence.content_retrieved)
        self.assertTrue(evidence.metadata_complete)
        self.assertEqual(evidence.observed_amendments, ["32024L2749"])
        self.assertEqual(len(post.queries), 2)
        self.assertIn(CONSOL_2, text)
        self.assertFalse(evidence.version_verified)
        self.assertFalse(evidence.legal_status_verified)

    def test_dated_query_does_not_fetch_future_consolidation(self):
        post, get = FakePost(), FakeGet()
        evidence, _ = probe_eurlex(
            CELEX, as_of=date(2025, 1, 1), post=post, get=get
        )
        self.assertEqual(evidence.selected_consolidation, CONSOL_1)
        self.assertTrue(all(CONSOL_2 not in url for url in get.urls))

    def test_no_consolidation_is_reported_not_invented(self):
        post, get = FakePost(versions=[]), FakeGet()
        evidence, text = probe_eurlex(CELEX, post=post, get=get)
        self.assertEqual(evidence.outcome, "no_applicable_consolidation")
        self.assertEqual(text, "")
        self.assertEqual(get.urls, [])
        self.assertFalse(evidence.version_verified)

    def test_browser_challenge_fails_closed(self):
        evidence, _ = probe_eurlex(CELEX, post=FakePost(), get=FakeGet(challenge=True))
        self.assertEqual(evidence.outcome, "source_unavailable")
        self.assertFalse(evidence.content_retrieved)
        self.assertFalse(evidence.version_verified)

    def test_redirect_to_untrusted_host_is_blocked(self):
        evidence, _ = probe_eurlex(CELEX, post=FakePost(), get=FakeGet(redirect=True))
        self.assertEqual(evidence.outcome, "source_unavailable")
        self.assertFalse(evidence.content_retrieved)

    def test_legacy_official_http_redirect_upgraded_to_https(self):
        get = FakeGet(legacy_redirect=True)
        evidence, text = probe_eurlex(CELEX, post=FakePost(), get=get)
        self.assertEqual(evidence.outcome, "source_text_retrieved")
        self.assertEqual(len(get.urls), 2)
        self.assertTrue(all(url.startswith("https://") for url in get.urls))
        self.assertIn("02010L0035", text)
        self.assertFalse(evidence.version_verified)

    def test_unknown_document_identity_is_not_verified(self):
        evidence, _ = probe_eurlex(
            CELEX, post=FakePost(), get=FakeGet(mismatched=True)
        )
        self.assertEqual(evidence.outcome, "source_identity_unconfirmed")
        self.assertFalse(evidence.document_identity_observed)
        self.assertFalse(evidence.version_verified)

    def test_result_cap_marks_metadata_incomplete(self):
        versions = [f"02010L0035-20{i//12+10:02d}{i%12+1:02d}01" for i in range(100)]
        evidence, _ = probe_eurlex(
            CELEX, post=FakePost(versions=versions), get=FakeGet(),
            as_of=date(2026, 11, 12),
        )
        self.assertFalse(evidence.metadata_complete)
        self.assertFalse(evidence.version_verified)


if __name__ == "__main__":
    unittest.main()
