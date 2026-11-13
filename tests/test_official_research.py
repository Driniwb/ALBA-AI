"""Safety tests for direct official links and continuity of short follow-ups."""
import unittest

from official_research import detect_reference, official_links, link_answer


class OfficialResearchTests(unittest.TestCase):
    def test_albanian_44_2023_link_is_real_identified_act(self):
        links = official_links("Më jep linkun e ligjit nr. 44/2023.")
        self.assertEqual(len(links), 1)
        self.assertEqual(
            links[0].url, "https://qbz.gov.al/eli/ligj/2023/06/15/44"
        )
        answer = link_answer("Më jep linkun e ligjit nr. 44/2023.")
        self.assertIn("arsimin parauniversitar", answer)
        self.assertIn("nuk është ligji", answer)

    def test_followup_resolves_previous_user_act_not_unrelated_chat(self):
        history = [
            {"role": "user", "content": "Analyze Directive (EU) 2019/520."},
            {"role": "assistant", "content": "The EU Directive requires review."},
        ]
        answer = link_answer("Më jep linkun e versionit të fundit.", history)
        self.assertIn("CELEX:32019L0520", answer)
        self.assertIn("/NIM/", answer)
        self.assertIsNone(link_answer("Më jep një link.", []))

    def test_eu_directive_links_national_transposition(self):
        links = official_links("Compare Germany and Spain on Directive 2009/16")
        self.assertEqual(links[0].scope, "official_eu_act")
        self.assertEqual(links[1].scope, "national_transposition")
        self.assertTrue(links[1].url.endswith("32009L0016"))

    def test_unknown_albanian_number_is_not_a_guessed_eli_act(self):
        links = official_links("Më gjej ligjin nr. 999/2025")
        self.assertTrue(links)
        self.assertEqual(links[0].scope, "search")
        self.assertNotIn("/eli/ligj/2025/01/01/999", links[0].url)
        self.assertIn("JO", links[0].note)

    def test_no_network_calls_are_hidden_in_link_building(self):
        self.assertIsNone(detect_reference("Read this document"))
        self.assertEqual(official_links("Which country has the highest fines?"), [])


if __name__ == "__main__":
    unittest.main()
