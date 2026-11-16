"""Mocked official retrieval, EU NIM comparison, QBZ direct ELI, source trace."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from legal_research_engine import (
    _download_html, _eu_text_excerpt, _nim_entries, research_for_chat,
    source_note,
)
from chat_backend import prepare_chat_messages


EU_TEXT = """<html><body><div id="document1">
<p>CELEX 32019L0520 Directive (EU) 2019/520</p>
<h2>Article 1</h2>
<p>This Directive lays down rules for electronic road toll interoperability.
The operation of those systems requires agreement, compliance and testing.</p>
<p>Scope and exclusions depend on the relevant provisions.</p>
</div></body></html>"""

NIM = """<html><body><main>
<h3>Germany Germany</h3><p>Transposition deadline(s): 19/10/2021</p>
<p>Number of measures: 2</p>
<a href="/legal-content/EN/NIM/?uri=CELEX:72021L0520DEU_123">German Road Toll Act on electronic systems</a>
<a href="/legal-content/EN/NIM/?uri=CELEX:72021L0520DEU_456">German Toll Enforcement Regulations</a>
<h3>Spain Spain</h3><p>Transposition deadline(s): 19/10/2021</p>
<p>Number of measures: 1</p>
<a href="/legal-content/EN/NIM/?uri=CELEX:72021L0520ESP_555">Spanish Toll Interoperability Law</a>
<h3>France France</h3><p>Number of measures: 7</p>
</main></body></html>"""


class Response:
    status_code = 200
    headers = {"Content-Type": "text/html; charset=UTF-8"}
    def __init__(self, text):
        self.content = text.encode("utf-8")
    def iter_content(self, chunk_size=65536):
        yield self.content


class LiveResearchTests(unittest.TestCase):
    def test_reads_exact_eu_act_and_notified_measures_from_realistic_html(self):
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            return Response(NIM if "/NIM/" in url else EU_TEXT)

        result = research_for_chat(
            "Compare Germany and Spain on Directive (EU) 2019/520.",
            jurisdictions=["Germany", "Spain"], get=get,
        )
        self.assertEqual(len(calls), 2)
        self.assertTrue(result.was_retrieved())
        self.assertIn("CELEX 32019L0520", result.evidence)
        self.assertIn("Article 1", result.evidence)
        self.assertIn("Germany", result.evidence)
        self.assertIn("2 notified", result.evidence)
        self.assertIn("Spanish Toll Interoperability", result.evidence)
        self.assertIn("NOT compliance determinations", result.evidence)
        self.assertIn("retrieved UTC", result.evidence)
        trace = source_note(result)
        self.assertIn("Official source trace", trace)
        self.assertIn("EUR-Lex", trace)

    def test_short_followup_finds_previous_user_directive(self):
        def get(url, **kwargs):
            return Response(NIM if "/NIM/" in url else EU_TEXT)
        history = [
            {"role": "user", "content": "Please check Directive 2019/520."},
            {"role": "assistant", "content": "Initial overview."},
        ]
        result = research_for_chat("And Germany?", history, get=get)
        self.assertIn("Germany", result.evidence)
        self.assertTrue(result.was_retrieved())

    def test_unknown_albanian_act_is_not_fabricated_as_eli(self):
        def forbidden(url, **kwargs):
            raise AssertionError("Unknown Albanian act should not be fetched.")
        result = research_for_chat(
            "Check ligji nr. 777/2024.", get=forbidden,
        )
        self.assertFalse(result.was_retrieved())
        self.assertEqual(result.evidence, "")

    def test_exact_user_eli_retrieves_actual_pdf_evidence(self):
        url = "https://qbz.gov.al/eli/ligj/2015/04/30/44"
        def fake_qbz(value):
            self.assertEqual(value, url)
            return (
                SimpleNamespace(
                    identity_observed=True, source_text_retrieved=True,
                    selected_file_url="https://qbz.gov.al/alfresco/webdav/Aktet/public.pdf",
                ),
                "KODI I PROCEDURAVE ADMINISTRATIVE – Article 1. Public test."
            )
        result = research_for_chat(
            f"Review {url}", qbz_retrieve=fake_qbz,
        )
        self.assertIn("KODI", result.evidence)
        self.assertTrue(result.was_retrieved())

    def test_rejects_redirect_to_unapproved_host_and_network_failure(self):
        class Redirect:
            status_code = 302
            headers = {"Location": "https://not-official.example/private"}
        with self.assertRaises(ValueError):
            _download_html(
                "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32019L0520",
                get=lambda url, **kwargs: Redirect(),
            )
        def failing(url, **kwargs):
            raise ValueError("upstream blocked")
        result = research_for_chat("Check Directive (EU) 2019/520", get=failing)
        self.assertFalse(result.was_retrieved())
        self.assertTrue(any("unavailable" in x for x in result.warnings))
        self.assertEqual(source_note(result), "")

    def test_html_parser_rejects_unidentified_document(self):
        self.assertEqual(_eu_text_excerpt("<html><body>Welcome</body></html>",
                                          "32019L0520", "Article 1"), "")
        count, measures = _nim_entries(NIM, "Germany")
        self.assertEqual(count, 2)
        self.assertEqual(len(measures), 2)
        self.assertEqual(_nim_entries("<html>Empty</html>", "Germany"), (None, []))

    def test_long_running_conversation_keeps_starting_topic_and_latest_turns(self):
        history = [
            {"role": "user", "content": "Review Directive 2019/520 for Albania."},
            {"role": "assistant", "content": "Initial answer."},
        ]
        for i in range(12):
            history.extend((
                {"role": "user", "content": f"Follow-up {i}: " + "A" * 320},
                {"role": "assistant", "content": f"Answer {i}: " + "B" * 410},
            ))
        req = prepare_chat_messages(
            mode="general", history=history, user_text="Continue the assessment.",
            research_evidence="[Official excerpt] Article 1 scope of directive.",
        )
        self.assertIn("Review Directive 2019/520", req[0]["content"])
        self.assertIn("Official excerpt", req[0]["content"])
        self.assertEqual(req[-1]["content"], "Continue the assessment.")
        self.assertTrue(any("Follow-up 11" in m["content"] for m in req))

    def test_research_context_cannot_overrun_model_prompt(self):
        with self.assertRaisesRegex(ValueError, "too large"):
            prepare_chat_messages(
                mode="general", history=[], user_text="Public research.",
                research_evidence="X" * 9001,
            )


if __name__ == "__main__":
    unittest.main()
