"""Public document ease-of-use regression tests for non-Legal ALBA modules.

No third-party services are contacted. All examples are synthetic and contain
legal-topic vocabulary, not actual personal/private records.
"""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from communication_studio import (
    build_messages, generate_communication, generate_social_bundle, load_library,
)
from privacy_guard import scan_text, scan_text_fields

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_TOPIC = (
    "Article 1. The authority shall safeguard confidential information "
    "and medical records according to the law."
)
PRIVATE_DATA = "Private contact: private.user@example.org"


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "success": True,
            "result": {
                "response": (
                    "### Materiali për publikim\n"
                    "Institucioni zbaton rregulla për medical records dhe konfidencialitetin.\n"
                    "### Për t'u verifikuar përpara publikimit\n"
                    "Kontrollo burimet e aktit publik."
                )
            },
        }


class PublicDocumentModulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.rules, cls.albanian = load_library()

    def test_public_vocabulary_is_accepted_but_personal_contact_is_not(self):
        self.assertFalse(scan_text(PUBLIC_TOPIC, public_legal=True).blocked)
        self.assertTrue(scan_text(PRIVATE_DATA, public_legal=True).blocked)
        self.assertTrue(scan_text_fields(
            "Classification: Confidential", public_legal=True
        ).blocked)

    def test_public_communication_pipeline_works_through_model_guard(self):
        source = PUBLIC_TOPIC
        request = build_messages(
            format_id="press_release", mode="create", source_text=source,
            organization="", audience="", objective="",
            visual_description="", communication_rules=self.rules,
            albanian_rules=self.albanian,
            public_legal_source=True,
        )
        self.assertIn(PUBLIC_TOPIC, request[1]["content"])
        result = generate_communication(
            request, "FAKE_ACCOUNT", "FAKE_TOKEN",
            public_legal_source=True,
            post=lambda url, **kwargs: FakeResponse(),
        )
        self.assertIn("konfidencialitetin", result)
        with self.assertRaises(ValueError):
            build_messages(
                format_id="press_release", mode="create", source_text=PRIVATE_DATA,
                organization="", audience="", objective="",
                visual_description="", communication_rules=self.rules,
                albanian_rules=self.albanian,
                public_legal_source=True,
            )

    def test_social_bundle_does_not_reblock_public_source_vocabulary(self):
        sent = []
        def fake_post(url, **kwargs):
            sent.append(url)
            return FakeResponse()
        bundle = generate_social_bundle(
            mode="create", source_text=PUBLIC_TOPIC,
            organization="", audience="", objective="",
            visual_description="", style_id="standard",
            communication_rules=self.rules,
            albanian_rules=self.albanian,
            account_id="FAKE_ACCOUNT", api_token="FAKE_TOKEN",
            post=fake_post, public_legal_source=True,
        )
        self.assertEqual(set(bundle), {"instagram", "linkedin", "facebook", "x"})
        self.assertEqual(len(sent), 4)

    def test_writing_assistant_accepts_public_topic_without_error(self):
        app = AppTest.from_file(str(ROOT / "writing_assistant.py"),
                                default_timeout=25).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(PUBLIC_TOPIC).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.error)

    def test_communication_studio_accepts_public_topic_without_error(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "2_Communication_Studio.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(PUBLIC_TOPIC).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.error)

    def test_eu_reporting_accepts_public_topic_without_error(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "4_EU_Reporting.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area[0].set_value(PUBLIC_TOPIC).run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.error)

    def test_toc_single_public_upload_is_screened_locally(self):
        src = (ROOT / "pages" / "1_ToC_Builder.py").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / "toc_workflow.py").read_text(encoding="utf-8")
        self.assertIn("prepare_toc(source.name, source.getvalue())", src)
        self.assertIn("screen_upload(", workflow)
        self.assertIn("public_legal=True", workflow)
        self.assertEqual(src.count("st.file_uploader("), 1)
        for file_name in (
            "writing_assistant.py",
            "pages/2_Communication_Studio.py",
            "pages/4_EU_Reporting.py",
        ):
            text = (ROOT / file_name).read_text(encoding="utf-8")
            self.assertIn("selected_public_attachment(", text)


if __name__ == "__main__":
    unittest.main()
