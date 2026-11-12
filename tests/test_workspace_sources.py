"""Source panel: only user-shared official links, never AI-verified claims."""
import unittest

from workspace_sources import official_link, user_source_links


class WorkspaceSourcesTests(unittest.TestCase):
    def test_recognizes_exact_official_act_links(self):
        qbz = official_link("https://qbz.gov.al/eli/ligj/2012/06/21/69")
        self.assertEqual(qbz["source"], "QBZ")
        eurlex = official_link(
            "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32010L0035"
        )
        self.assertEqual(eurlex["source"], "EUR-Lex")
        self.assertIn("32010L0035", eurlex["label"])

    def test_no_spoofed_hosts_or_unofficial_schemes(self):
        for link in (
            "http://qbz.gov.al/eli/ligj/2012/06/21/69",
            "https://qbz.gov.al.evil.test/eli/ligj/2012/06/21/69",
            "https://evil.test/eli/ligj/2012/06/21/69",
            "https://eur-lex.europa.eu@attacker.test/legal-content/EN/TXT/",
            "https://qbz.gov.al/",
            "https://eur-lex.europa.eu.evil.test/legal-content/EN/TXT/",
            "https://qbz.gov.al:bad/eli/ligj/2012/06/21/69",
        ):
            with self.subTest(link=link):
                self.assertIsNone(official_link(link))

    def test_only_user_supplied_links_not_ai_generated_claims(self):
        messages = [
            {"role": "assistant", "content": (
                "I invented https://qbz.gov.al/eli/ligj/2012/06/21/99"
            )},
            {"role": "user", "content": (
                "Check https://qbz.gov.al/eli/ligj/2012/06/21/69. "
                "And https://eur-lex.europa.eu/legal-content/EN/TXT/"
                "?uri=CELEX%3A32010L0035"
            )},
            {"role": "assistant", "content": "No verified retrieval has occurred."},
        ]
        sources = user_source_links(messages)
        self.assertEqual(len(sources), 2)
        self.assertTrue(all("99" not in source["url"] for source in sources))

    def test_duplicates_limits_and_markdown_punctuation(self):
        messages = [
            {"role": "user", "content": (
                "(https://qbz.gov.al/eli/ligj/2012/06/21/69), "
                "https://qbz.gov.al/eli/ligj/2012/06/21/69 "
                "https://eur-lex.europa.eu/eli/dir/2010/35/oj/eng"
            )}
        ]
        self.assertEqual(len(user_source_links(messages)), 2)
        self.assertEqual(len(user_source_links(messages, limit=1)), 1)


if __name__ == "__main__":
    unittest.main()
