"""Streamlit front-end smoke tests without external credentials or documents."""
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class StreamlitNavigationSmoke(unittest.TestCase):
    def test_main_editor_loads_without_cloudflare_secrets(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
        self.assertEqual(len(app.exception), 0)

    def test_toc_builder_page_loads_without_upload(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "1_ToC_Builder.py"), default_timeout=25
        ).run()
        self.assertEqual(len(app.exception), 0)
        headings = [item.value for item in app.title]
        self.assertTrue(any("ToC Builder" in value for value in headings))


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


    def test_main_editor_blocks_contact_details_without_echo(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
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
