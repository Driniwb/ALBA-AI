"""Offline test suite for official Cellar corrigendum document recovery."""
from datetime import date
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from eurlex_corrigenda import (
    _resolve_work, _get_official_xhtml, _heading_ok, _target,
    _crosscheck, _expression_languages, inspect_corrigendum,
    review_amendment_corrigenda, work_query, language_query,
)

WORK_ID = "28137a49-1f13-11f0-b1a3-01aa75ed71a1"
WORK = "https://publications.europa.eu/resource/cellar/" + WORK_ID
CELEX = "32024L2749R(01)"
ORIGINAL = (
    "9. The use of the authorisation procedure set out in paragraphs "
    "1 to 4 of this Article shall not affect the application on the territory "
    "of the Member State concerned of the relevant conformity assessment "
    "procedures laid down in Article 18."
)
CORRECTED = ORIGINAL.replace("Article 18", "Article 12")
CONSOLIDATED = "Article 33c Derogation from conformity assessment 9. " + CORRECTED
TEXT = (
    "L_202590340EN.000101.fmx.xml Official Journal of the European Union "
    "EN L series 2025/90340 22.4.2025 Corrigendum to Directive (EU) "
    "2024/2749 of the European Parliament and of the Council of 9 October "
    "2024 amending Directives 2000/14/EC, 2006/42/EC, 2010/35/EU "
    "On page 14, Article 3, point (2), concerning Article 33c(9) of "
    "Directive 2010/35/EU: for: ‘" + ORIGINAL + "’ , read: ‘" + CORRECTED + "’."
)


class Response:
    def __init__(self, *, code=200, text="", mime="application/xhtml+xml", redirect=""):
        self.status_code = code
        self.text = text
        self.content = text.encode("utf-8")
        self.headers = {"Content-Type": mime}
        if redirect:
            self.headers["Location"] = redirect


def row(uri):
    return {"work": {"type": "uri", "value": uri}}


class CorrigendaTests(unittest.TestCase):
    def test_query_uses_exact_celex_and_limited_official_metadata(self):
        q = work_query(CELEX)
        self.assertIn('"32024L2749R(01)"^^xsd:string', q)
        self.assertIn("LIMIT 10", q)
        for x in ("32024L2749", "32024L2749R(01) UNION", "32024L2749R(100)"):
            with self.subTest(x=x):
                with self.assertRaises(ValueError):
                    work_query(x)

    def test_unique_work_only_and_official_work_host(self):
        with patch("eurlex_corrigenda._rows", return_value=[row("http://" + WORK[8:])]):
            self.assertEqual(_resolve_work(CELEX, post=object()), WORK)
        for fake in ([], [row("https://attacker.example/resource/cellar/" + WORK_ID)],
                     [row(WORK), row("https://publications.europa.eu/resource/cellar/"
                                    "11111111-2222-3333-4444-555555555555")]):
            with self.subTest(fake=fake):
                with patch("eurlex_corrigenda._rows", return_value=fake):
                    with self.assertRaises(ValueError):
                        _resolve_work(CELEX, post=object())

    def test_follows_only_same_official_work_and_https(self):
        called = []
        def fake_get(url, **kwargs):
            called.append(url)
            self.assertFalse(kwargs["allow_redirects"])
            if len(called) == 1:
                return Response(code=303, redirect=(
                    "http://publications.europa.eu/resource/cellar/"
                    + WORK_ID + ".0006.03/DOC_1"
                ))
            return Response(text="<html><body>" + TEXT + "</body></html>")
        url, text = _get_official_xhtml(WORK, get=fake_get)
        self.assertIn("Article 12", text)
        self.assertTrue(url.startswith("https://"))
        self.assertTrue(all(u.startswith("https://") for u in called))

    def test_cross_work_or_attacker_redirect_fails(self):
        for address in (
            "https://attacker.example/resource/cellar/evil/DOC_1",
            "https://publications.europa.eu/resource/cellar/"
            "11111111-2222-3333-4444-555555555555.0006.03/DOC_1",
            "https://publications.europa.eu/resource/cellar/" + WORK_ID
            + "/../../secret",
        ):
            with self.subTest(address=address):
                def redirecting(url, **kwargs):
                    return Response(code=303, redirect=address)
                with self.assertRaises(ValueError):
                    _get_official_xhtml(WORK, get=redirecting)

    def test_target_and_language_are_read_from_source_not_assumed(self):
        self.assertTrue(_heading_ok(TEXT, CELEX))
        self.assertFalse(_heading_ok(TEXT.replace(" EN L series", " FR L series"), CELEX))
        self.assertEqual(_target(TEXT), ("32010L0035", "33c", "9"))
        self.assertEqual(_target(TEXT.replace("Directive 2010/35/EU", "a summary")), (None, None, None))

    def test_exact_correction_matches_current_consolidated_paragraph(self):
        self.assertTrue(_crosscheck(CORRECTED, ORIGINAL, CONSOLIDATED))
        self.assertFalse(_crosscheck(CORRECTED, ORIGINAL,
                                    CONSOLIDATED.replace("Article 12", "Article 18")))
        self.assertIsNone(_crosscheck(CORRECTED, ORIGINAL, ""))

    def _fake_inspect(self, *, text=TEXT, consolidated=CONSOLIDATED,
                      as_of=date(2026, 11, 12)):
        def get(url, **kwargs):
            return Response(text="<html><body>" + text + "</body></html>")
        def source_rows(query, *, post, row_limit):
            if "SELECT DISTINCT ?language" in query:
                return [{"language": {"type": "uri",
                          "value": "http://publications.europa.eu/resource/authority/language/ENG"}}]
            return [row("http://" + WORK[8:])]
        with patch("eurlex_corrigenda._rows", side_effect=source_rows):
            return inspect_corrigendum(
                CELEX, base_celex="32010L0035",
                provision_article="33c", provision_paragraph="9",
                consolidated_provision=consolidated,
                as_of=as_of, post=object(), get=get,
            )

    def test_detects_relevant_english_corrigendum_and_preserves_sources(self):
        result = self._fake_inspect()
        self.assertEqual(result.outcome, "corrected_text_consistent_with_consolidation")
        self.assertTrue(result.heading_confirmed)
        self.assertTrue(result.language_confirmed)
        self.assertEqual(result.available_languages, ["ENG"])
        self.assertTrue(result.language_scope_checked)
        self.assertEqual(result.published_date, "2025-04-22")
        self.assertEqual(result.target_base_celex, "32010L0035")
        self.assertEqual(result.affects_requested_provision, True)
        self.assertTrue(result.corrected_text_matches_consolidation)
        self.assertIn("Article 18", result.before_text)
        self.assertIn("Article 12", result.after_text)
        self.assertTrue(result.official_content_url.startswith("https://"))
        self.assertFalse(result.fully_legally_verified)

    def test_unrelated_provision_does_not_become_relevant(self):
        result = self._fake_inspect(text=TEXT.replace(
            "Article 33c(9) of Directive 2010/35/EU",
            "Article 38d(5) of Directive 2014/34/EU"
        ))
        self.assertEqual(result.outcome, "other_provision_or_act")
        self.assertFalse(result.affects_requested_provision)
        self.assertIsNone(result.corrected_text_matches_consolidation)

    def test_future_publication_not_effective_before_date(self):
        result = self._fake_inspect(as_of=date(2025, 4, 1))
        self.assertEqual(result.outcome, "not_published_at_requested_date")
        self.assertIsNone(result.affects_requested_provision)
        self.assertFalse(result.fully_legally_verified)

    def test_bad_identity_and_unknown_scope_fail_closed(self):
        mismatched = self._fake_inspect(text=TEXT.replace(
            "Corrigendum to Directive (EU) 2024/2749",
            "Corrigendum to Directive (EU) 2024/1111"
        ))
        self.assertEqual(mismatched.outcome, "document_identity_unconfirmed")
        self.assertIsNone(mismatched.affects_requested_provision)
        unknown = self._fake_inspect(text=TEXT.replace(
            "concerning Article 33c(9) of Directive 2010/35/EU",
            "concerning another legal instrument"
        ))
        self.assertEqual(unknown.outcome, "target_unconfirmed")

    def test_language_query_uses_documented_inverse_wemi_relation(self):
        q = language_query("32024L2749R(03)")
        self.assertIn("cdm:expression_belongs_to_work", q)
        self.assertIn("cdm:expression_uses_language", q)
        self.assertIn("LIMIT 80", q)

    def test_non_english_oj_corrected_language_is_not_missing_document(self):
        for celex, language in (
            ("32024L2749R(03)", "LAV"),
            ("32024L2749R(04)", "SWE"),
        ):
            with self.subTest(celex=celex):
                def rows(query, *, post, row_limit):
                    if "SELECT DISTINCT ?language" in query:
                        return [{"language": {
                            "type": "uri",
                            "value": "http://publications.europa.eu/resource/authority/language/"
                                     + language
                        }}]
                    return [row(WORK)]
                def should_not_download(*args, **kwargs):
                    raise AssertionError("Non-English text must not be fetched as English")
                with (
                    patch("eurlex_corrigenda._rows", side_effect=rows),
                    patch("eurlex_corrigenda._get_official_xhtml",
                          side_effect=should_not_download),
                ):
                    result = inspect_corrigendum(
                        celex, base_celex="32010L0035",
                        provision_article="33c", provision_paragraph="9",
                        consolidated_provision=CONSOLIDATED,
                    )
                self.assertEqual(result.outcome, "not_published_in_english")
                self.assertEqual(result.available_languages, [language])
                self.assertTrue(result.language_scope_checked)
                self.assertFalse(result.english_version_available)
                self.assertFalse(result.affects_requested_provision)
                self.assertFalse(result.fully_legally_verified)

    def test_unknown_language_metadata_never_implies_no_english(self):
        def rows(query, *, post, row_limit):
            return [] if "SELECT DISTINCT ?language" in query else [row(WORK)]
        with patch("eurlex_corrigenda._rows", side_effect=rows):
            with patch("eurlex_corrigenda._get_official_xhtml",
                       return_value=(WORK + ".0006.03/DOC_1", TEXT)):
                report = inspect_corrigendum(
                    CELEX, base_celex="32010L0035",
                    provision_article="33c", provision_paragraph="9",
                    consolidated_provision=CONSOLIDATED,
                )
        self.assertFalse(report.language_scope_checked)
        self.assertIsNone(report.english_version_available)
        self.assertTrue(report.official_text_retrieved)

    def test_orchestrator_separates_relevant_unrelated_and_unknown(self):
        oj = SimpleNamespace(
            observed_corrigenda_celex=[
                "32024L2749R(01)", "32024L2749R(02)", "32024L2749R(03)"
            ],
            corrigendum_discovery_checked=True,
            provision_text=CONSOLIDATED,
            unresolved=["Emergency mode remains conditional."],
        )
        def fake_inspect(celex, **kwargs):
            defaults = {
                "32024L2749R(01)": (True, True, True),
                "32024L2749R(02)": (False, None, True),
                "32024L2749R(03)": (None, None, False),
            }
            relevant, exact, retrieved = defaults[celex]
            return SimpleNamespace(
                celex=celex, affects_requested_provision=relevant,
                corrected_text_matches_consolidation=exact,
                official_text_retrieved=retrieved, heading_confirmed=retrieved,
                language_confirmed=retrieved, language_scope_checked=retrieved,
                english_version_available=True if retrieved else None,
            )
        with (
            patch("eurlex_corrigenda.review_oj_amendment", return_value=oj),
            patch("eurlex_corrigenda.inspect_corrigendum", side_effect=fake_inspect),
        ):
            report = review_amendment_corrigenda(
                "32010L0035", "32024L2749",
                article="33c", paragraph="9"
            )
        self.assertEqual(report.relevant_corrigenda, ["32024L2749R(01)"])
        self.assertEqual(report.unrelated_corrigenda, ["32024L2749R(02)"])
        self.assertEqual(report.unresolved_corrigenda, ["32024L2749R(03)"])
        self.assertTrue(report.exact_correction_match_confirmed)
        self.assertFalse(report.all_corrigendum_texts_retrieved)
        self.assertFalse(report.english_scope_complete)
        self.assertFalse(report.full_legal_verification)
        self.assertEqual(report.outcome, "corrigendum_review_incomplete")


if __name__ == "__main__":
    unittest.main()
