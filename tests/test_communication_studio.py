"""Offline ALBA Communication Studio tests; no real API calls or user files."""
import ast
from pathlib import Path
import unittest

from communication_studio import (
    FORMATS,
    SOCIAL_STYLES,
    EU_REPORTING_FORMATS,
    generate_social_bundle,
    applicable_rules,
    albanian_editorial_rules,
    build_messages,
    extract_ai_text,
    extract_publishable_text,
    generate_communication,
    load_library,
    qa_flags,
    validate_library,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "success": True,
            "result": {
                "response": (
                    "### Materiali për publikim\n"
                    "Hapet konsultimi publik në Tiranë.\n\n"
                    "### Për t'u verifikuar përpara publikimit\n"
                    "Verifikoni datën e konsultimit."
                )
            },
        }


class CommunicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources, cls.rules, cls.albanian = load_library()

    def test_30_rules_and_11_public_sources(self):
        self.assertEqual(len(self.rules), 30)
        self.assertEqual(len(self.sources), 11)
        self.assertEqual(
            {r["rule_id"] for r in self.rules},
            {f"C{i:02}" for i in range(1,31)},
        )
        validate_library(self.sources, self.rules)

    def test_rules_are_format_specific_not_all_30(self):
        self.assertEqual(len(FORMATS), 13)
        ids = lambda k: [r["rule_id"] for r in applicable_rules(k, self.rules)]
        self.assertEqual(ids("instagram"), [
            "C01","C02","C03","C04","C05","C06","C07","C08",
            "C23","C24","C25","C26","C27"
        ])
        self.assertIn("C11", ids("press_release"))
        self.assertNotIn("C11", ids("press_statement"))
        self.assertIn("C18", ids("newsletter"))
        self.assertIn("C30", ids("x"))
        self.assertEqual(len(ids("x")), 13)

    def test_five_eu_reporting_formats_and_language_control(self):
        self.assertEqual(
            EU_REPORTING_FORMATS,
            frozenset({
                "eu_letter", "information_note", "administrative_capacity",
                "progress_report", "negotiating_position",
            }),
        )
        base = dict(
            format_id="administrative_capacity", mode="create",
            source_text="Public synthetic assessment of one competent authority.",
            organization="Ministry Demo", audience="European Commission",
            objective="Summarise legally assigned competences and evidence",
            visual_description="",
            communication_rules=self.rules, albanian_rules=self.albanian,
        )
        output = build_messages(**base, output_language="en")
        self.assertIn("Output the draft in English", output[0]["content"])
        self.assertIn("FTE", output[0]["content"])
        self.assertIn("operational implementation", output[0]["content"])
        self.assertIn("Administrative Capacity Note", output[1]["content"])
        self.assertIn("English", output[1]["content"])
        sq = build_messages(**base, output_language="sq")
        self.assertIn("Output the draft in Albanian", sq[0]["content"])
        with self.assertRaises(ValueError):
            build_messages(**{**base, "format_id":"facebook"}, output_language="en")

    def test_eu_reporting_excludes_public_media_and_historic_language_rules(self):
        messages = build_messages(
            format_id="information_note", mode="review",
            source_text="This is a synthetic public progress report with no private data.",
            organization="Demo authority", audience="European Commission",
            objective="Explain evidenced progress", visual_description="",
            communication_rules=self.rules, albanian_rules=self.albanian,
            output_language="en",
        )
        self.assertIn("REFERENCE APPROACH:", messages[1]["content"])
        self.assertIn("English", messages[1]["content"])
        self.assertNotIn("R17:", messages[1]["content"])
        self.assertNotIn("C01:", messages[1]["content"])
        self.assertNotIn("Shënim: R17", messages[1]["content"])

    def test_social_bundle_generates_four_separate_platform_outputs(self):
        seen = []
        def fake_post(url, **kwargs):
            user = kwargs["json"]["messages"][1]["content"]
            seen.append(user)
            return FakeResponse()
        result = generate_social_bundle(
            mode="create", source_text="Public transport consultation was held.",
            organization="", audience="All residents",
            objective="Information", visual_description="",
            style_id="elevated", communication_rules=self.rules,
            albanian_rules=self.albanian, account_id="FAKE", api_token="TOKEN",
            post=fake_post,
        )
        self.assertEqual(set(result), {"instagram", "linkedin", "facebook", "x"})
        self.assertEqual(len(seen), 4)
        for platform in ("Instagram caption", "LinkedIn post", "Facebook post", "X (Twitter) post"):
            self.assertTrue(any(platform in message for message in seen))
        self.assertTrue(all("Stil editorial" in message for message in seen))

    def test_eu_draft_extraction_excludes_verification_section(self):
        example = (
            "### Draft for transmission\n"
            "The authority has submitted its assessment.\n"
            "### Verification before submission\n"
            "Confirm the staff and inspection data."
        )
        self.assertEqual(
            extract_publishable_text(example),
            "The authority has submitted its assessment."
        )

    def test_albanian_rules_reused_from_existing_library(self):
        ids = [r["rule_id"] for r in albanian_editorial_rules(self.albanian)]
        self.assertIn("R03", ids)
        self.assertIn("R17", ids)
        self.assertIn("R16", ids)

    def test_input_is_kept_as_source_and_no_rules_of_other_channel(self):
        brief = "Më 11 nëntor u mbajt aktiviteti publik me 12 pjesëmarrës."
        messages = build_messages(
            format_id="linkedin", mode="create", source_text=brief,
            organization="Organizata Demo", audience="Ekspertë",
            objective="Informim", visual_description="",
            communication_rules=self.rules,
            albanian_rules=self.albanian,
        )
        self.assertEqual(len(messages), 2)
        self.assertIn(brief, messages[1]["content"])
        self.assertIn("C28", messages[1]["content"])
        self.assertNotIn("C29", messages[1]["content"])
        self.assertIn("R03", messages[1]["content"])
        self.assertIn("Organizata Demo", messages[1]["content"])

    def test_social_elevator_and_elevated_styles_are_applied_only_to_social(self):
        self.assertEqual(set(SOCIAL_STYLES), {"standard", "elevator", "elevated"})
        base = dict(
            format_id="linkedin",
            mode="adapt",
            source_text="A verified public transport consultation took place.",
            organization="Demo",
            audience="Transport specialists",
            objective="Share verifiable information",
            visual_description="",
            communication_rules=self.rules,
            albanian_rules=self.albanian,
        )
        elevator = build_messages(**base, style_id="elevator")
        elevated = build_messages(**base, style_id="elevated")
        self.assertIn("elevator pitch", elevator[1]["content"])
        self.assertIn("Stil editorial", elevated[1]["content"])
        self.assertNotEqual(elevator[1]["content"], elevated[1]["content"])
        for platform in ("instagram", "linkedin", "facebook", "x"):
            self.assertEqual(len(build_messages(
                **{**base, "format_id": platform}, style_id="elevator"
            )), 2)
        with self.assertRaisesRegex(ValueError, "cannot be applied"):
            build_messages(
                **{**base, "format_id": "press_release"}, style_id="elevator"
            )
        with self.assertRaisesRegex(ValueError, "not supported"):
            build_messages(**base, style_id="unrecognized")

    def test_input_fails_when_missing_or_invalid_mode(self):
        base = dict(
            format_id="instagram", mode="create", source_text="",
            organization="", audience="", objective="", visual_description="",
            communication_rules=self.rules, albanian_rules=self.albanian,
        )
        with self.assertRaisesRegex(ValueError, "material faktik"):
            build_messages(**base)
        with self.assertRaisesRegex(ValueError, "mënyra"):
            build_messages(**{**base, "mode":"wrong"})

    def test_model_request_is_explicit_and_mocked(self):
        requests_seen = []
        def post(url, **kwargs):
            requests_seen.append((url,kwargs))
            return FakeResponse()
        messages = build_messages(
            format_id="press_release", mode="create",
            source_text="Konsultimi publik u hap në Tiranë.",
            organization="", audience="", objective="", visual_description="",
            communication_rules=self.rules, albanian_rules=self.albanian,
        )
        result = generate_communication(messages,"TEST_ACCOUNT","TEST_TOKEN",post=post)
        self.assertIn("Materiali për publikim",result)
        self.assertEqual(len(requests_seen),1)
        self.assertIn("@cf/google/gemma-4-26b-a4b-it",requests_seen[0][0])
        self.assertEqual(requests_seen[0][1]["headers"]["Authorization"],"Bearer TEST_TOKEN")
        self.assertFalse(requests_seen[0][1]["json"]["chat_template_kwargs"]["enable_thinking"])

    def test_extract_only_publishable_part(self):
        result = FakeResponse().json()["result"]["response"]
        text = extract_publishable_text(result)
        self.assertEqual(text,"Hapet konsultimi publik në Tiranë.")
        self.assertNotIn("Verifikoni datën",text)

    def test_detects_new_numbers_and_links_and_x_length(self):
        source = "Organizata hapi konsultimin më 11 nëntor."
        output = (
            "### Materiali për publikim\n"
            "Më 12 nëntor, organizata hapi konsultimin. "
            "https://example.invalid/\n\n"
            "### Për t'u verifikuar përpara publikimit\nAsnjë."
        )
        issues = qa_flags(source, output,"x")
        self.assertTrue(any("numbers" in msg for msg in issues))
        self.assertTrue(any("links" in msg for msg in issues))
        long_output = "### Materiali për publikim\n" + ("a"*281)
        self.assertTrue(any("280" in msg for msg in qa_flags("",long_output,"x")))

    def test_newsletter_subtitle_check(self):
        no_subject = "### Materiali për publikim\nPërshëndetje, miq."
        flags = qa_flags("Përshëndetje",no_subject,"newsletter")
        self.assertTrue(any("subject line" in x for x in flags))
        self.assertTrue(any("preview text" in x for x in flags))
        complete = (
            "### Materiali për publikim\n"
            "Subjekti: Lajmet mujore\n"
            "Teksti paraprak: Raportet e fundit\n"
            "Përmbajtja: Informacion i verifikuar\n"
            "### Për t'u verifikuar përpara publikimit\nAsnjë."
        )
        self.assertFalse(any("subject line" in x for x in qa_flags(
            "Raportet e fundit",complete,"newsletter"
        )))

    def test_api_does_not_accept_truncated_response(self):
        with self.assertRaisesRegex(ValueError,"ndërpre"):
            extract_ai_text({"result":{"choices":[{
                "finish_reason":"length",
                "message":{"content":"Gjysmë përgjigjeje"},
            }]}})
        with self.assertRaises(ValueError):
            extract_ai_text({"success":False, "errors":[]})

    def test_streamlit_page_is_valid_python(self):
        page = ROOT / "pages" / "2_Communication_Studio.py"
        self.assertTrue(page.is_file())
        ast.parse(page.read_text(encoding="utf-8"))


if __name__=="__main__":
    unittest.main()
