"""Streamlit front-end smoke tests without external credentials or documents."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class StreamlitNavigationSmoke(unittest.TestCase):
    def test_main_editor_loads_without_cloudflare_secrets(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
        self.assertEqual(len(app.exception), 0)

    def test_writing_assistant_named_page_loads(self):
        app = AppTest.from_file(
            str(ROOT / "writing_assistant.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            "Writing Assistant" in title.value for title in app.title
        ))

    def test_toc_builder_page_loads_without_upload(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        headings = [item.value for item in app.title]
        self.assertTrue(any("ToC Builder" in value for value in headings))


    def test_toc_article_range_and_empty_title(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.text_input[0].value, "")
        self.assertEqual(list(app.selectbox[0].options), [str(n) for n in range(1, 9)])

    def test_toc_mode_selection_removed(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any("Content of column 2" in str(x.label) for x in app.radio))

    def test_social_media_style_dropdown(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any("Post style" in str(x.label) for x in app.selectbox))
        app.selectbox[0].set_value("Social Media").run()
        self.assertEqual(len(app.exception), 0)
        styles = [x for x in app.selectbox if str(x.label) == "4. Post style"]
        self.assertEqual(len(styles), 1)
        self.assertIn("Elevator pitch – concise & compelling", styles[0].options)
        self.assertIn("Elevated editorial – polished & understated", styles[0].options)

    def test_communication_studio_page_loads_without_credentials(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            "Communication Studio" in item.value for item in app.title
        ))


    def test_communication_categories_and_platforms_are_navigable(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.selectbox[0].value, "Press & Media")
        self.assertIn("Press release", app.selectbox[1].options)
        app.selectbox[0].set_value("Social Media").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            list(app.selectbox[1].options),
            ["Instagram caption", "LinkedIn post", "Facebook post", "X (Twitter) post"],
        )
        app.radio[0].set_value("Adapt for selected platform").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.session_state["comm_mode"], "adapt")


    def test_legal_drafting_page_and_four_act_types(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "3_Legal_Drafting.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Legal Drafting" in item.value for item in app.title))
        self.assertIn("Draft law", app.selectbox[0].options)
        self.assertIn("Council of Ministers decision (VKM)", app.selectbox[0].options)
        self.assertIn("Ministerial instruction (udhëzim)", app.selectbox[0].options)
        self.assertIn("Regulation / technical rules (rregullore)", app.selectbox[0].options)

    def test_eu_reporting_formats_and_language_menu(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        app.selectbox[0].set_value("EU Communication & Reporting").run()
        self.assertEqual(len(app.exception), 0)
        labels = app.selectbox[1].options
        self.assertIn("Administrative Capacity Note", labels)
        self.assertIn("Information Note", labels)
        self.assertIn("Benchmark / Acquis Progress Report", labels)
        self.assertTrue(any(str(x.label) == "4. Reporting language" for x in app.selectbox))

    def test_eu_reporting_has_dedicated_page_in_alba_navigation(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"pages/3_Legal_Drafting.py"', source)
        self.assertIn('"pages/4_EU_Reporting.py"', source)
        self.assertIn('title="EU Communication & Reporting"', source)

        app = AppTest.from_file(
            str(ROOT / "pages" / "4_EU_Reporting.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            "EU Communication & Reporting" in item.value for item in app.title
        ))
        self.assertEqual(
            list(app.selectbox[0].options),
            [
                "Information Note",
                "Administrative Capacity Note",
                "Benchmark / Acquis Progress Report",
                "Negotiating Position – Section Draft",
                "Reply to the European Commission",
            ],
        )
        self.assertEqual(list(app.selectbox[1].options), ["English", "Albanian"])
        self.assertTrue(any(
            "Generate EU reporting draft" in str(x.label) for x in app.button
        ))

    def test_dedicated_eu_reporting_rejects_private_contacts_before_generation(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "4_EU_Reporting.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(
            "Private contact: fictional.example@example.org"
        ).run()
        self.assertEqual(len(app.exception), 0)
        errors = [str(x.value) for x in app.error]
        self.assertTrue(any("ALBA blocked processing" in x for x in errors))
        self.assertFalse(any("example.org" in x for x in errors))

    def test_social_campaign_generate_control_visible_only_on_social(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertFalse(any(
            "Generate posts for all four platforms" in str(x.label) for x in app.button
        ))
        app.selectbox[0].set_value("Social Media").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            "Generate posts for all four platforms" in str(x.label) for x in app.button
        ))

    def test_main_editor_blocks_contact_details_without_echo(self):
        app = AppTest.from_file(str(ROOT / "writing_assistant.py"), default_timeout=25).run()
        app.text_area[0].set_value("Private contact: synthetic.person@example.org").run()
        self.assertEqual(len(app.exception), 0)
        messages = [str(item.value) for item in app.error]
        self.assertTrue(any("ALBA blocked processing" in item for item in messages))
        self.assertFalse(any("example.org" in item for item in messages))

    def test_communication_page_blocks_contact_details_without_echo(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        app.text_area[0].set_value("Person: synthetic.person@example.org").run()
        self.assertEqual(len(app.exception), 0)
        messages = [str(item.value) for item in app.error]
        self.assertTrue(any("ALBA blocked processing" in item for item in messages))
        self.assertFalse(any("example.org" in item for item in messages))



if __name__ == "__main__":
    unittest.main()
