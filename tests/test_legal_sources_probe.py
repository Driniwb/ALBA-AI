"""Offline regression tests for legal-source pilot. No network or model calls."""
import json
from datetime import date
from pathlib import Path
import unittest

from legal_sources_probe import (
    probe_case, run_manifest, validate_official_url,
)


class FakeResponse:
    def __init__(self, text, *, status=200, content_type="text/html", location=None):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        if location is not None:
            self.headers["Location"] = location


def fake_get(response):
    def get(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] > 0
        return response
    return get


AL_CASE = {
    "id": "AL-02", "jurisdiction": "AL",
    "url": "https://qbz.gov.al/eli/ligj/2012/06/21/69",
}
EU_CASE = {
    "id": "EU-02", "jurisdiction": "EU",
    "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32010L0035",
}


class LegalSourcesProbeTests(unittest.TestCase):
    def test_manifest_has_ten_official_cases_per_jurisdiction(self):
        path = Path(__file__).parent / "fixtures" / "legal_source_pilot_20.json"
        cases = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 20)
        self.assertEqual(len({case["id"] for case in cases}), 20)
        self.assertEqual(sum(c["jurisdiction"] == "AL" for c in cases), 10)
        self.assertEqual(sum(c["jurisdiction"] == "EU" for c in cases), 10)
        for case in cases:
            with self.subTest(case=case["id"]):
                validate_official_url(case["url"], case["jurisdiction"])
                self.assertEqual(case["expected_verification"], "UNKNOWN_UNTIL_LIVE_CHECK")

    def test_qbz_version_candidate_does_not_certify_consolidation(self):
        html = """<html><script>HIDE DATA</script><body>
        Nr. i aktit 69 Data e aktit 21/06/2012
        Permalink ELI https://qbz.gov.al/eli/ligj/2012/06/21/69
        Versioni 1, në fuqi nga 28/03/2019
        Versioni 3, në fuqi nga 12/09/2024
        Versioni 4, në fuqi nga 05/03/2026
        </body></html>"""
        result = probe_case(AL_CASE, get=fake_get(FakeResponse(html)),
                            as_of=date(2026, 11, 12))
        self.assertEqual(result.outcome, "identity_candidate")
        self.assertTrue(result.identity_observed)
        self.assertEqual(result.candidate_version_date, "2026-03-05")
        self.assertFalse(result.version_verified)
        self.assertFalse(result.status_verified)

    def test_dated_request_does_not_select_future_version(self):
        html = """Nr. i aktit 69 Data e aktit 21/06/2012 Permalink ELI
        Versioni 1, në fuqi nga 28/03/2019
        Versioni 4, në fuqi nga 05/03/2026"""
        result = probe_case(AL_CASE, get=fake_get(FakeResponse(html, content_type="text/plain")),
                            as_of=date(2025, 1, 1))
        self.assertEqual(result.candidate_version_date, "2019-03-28")
        self.assertFalse(result.version_verified)

    def test_http_200_without_evidence_is_not_verified(self):
        result = probe_case(AL_CASE, get=fake_get(FakeResponse(
            "<html><body>Welcome to QBZ legal portal</body></html>"
        )))
        self.assertEqual(result.outcome, "document_unconfirmed")
        self.assertFalse(result.identity_observed)
        self.assertFalse(result.version_verified)

    def test_eurlex_challenge_is_not_a_legal_source(self):
        result = probe_case(EU_CASE, get=fake_get(FakeResponse(
            "In order to continue, we need to verify that you're not a robot."
        )))
        self.assertEqual(result.outcome, "access_challenge")
        self.assertFalse(result.status_verified)

    def test_eurlex_visible_id_still_does_not_certify_in_force(self):
        result = probe_case(EU_CASE, get=fake_get(FakeResponse(
            "CELEX 32010L0035 Directive 2010/35/EU In force"
        )))
        self.assertEqual(result.outcome, "identity_candidate")
        self.assertFalse(result.version_verified)
        self.assertFalse(result.status_verified)

    def test_official_host_allowlist_blocks_spoofing(self):
        for url in (
            "http://qbz.gov.al/eli/ligj/2012/06/21/69",
            "https://qbz.gov.al.attacker.example/eli/ligj/2012/06/21/69",
            "https://example.com/eli/ligj/2012/06/21/69",
            "https://qbz.gov.al/evil/other",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    validate_official_url(url, "AL")

    def test_redirect_to_nonofficial_domain_is_rejected(self):
        result = probe_case(AL_CASE, get=fake_get(
            FakeResponse("", status=302, location="https://evil.example/page")
        ))
        self.assertEqual(result.outcome, "redirect_blocked")
        self.assertFalse(result.identity_observed)

    def test_http_error_and_html_malformed_do_not_claim_verification(self):
        result = probe_case(AL_CASE, get=fake_get(FakeResponse("", status=429)))
        self.assertEqual(result.outcome, "http_error")
        self.assertFalse(result.version_verified)

    def test_manifest_rejects_duplicate_cases(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            run_manifest([AL_CASE, dict(AL_CASE)], get=fake_get(FakeResponse("")))


if __name__ == "__main__":
    unittest.main()
