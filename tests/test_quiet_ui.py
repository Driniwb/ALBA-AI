"""UI decluttering regressions: fewer notes without removing safeguards."""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class QuietUiTests(unittest.TestCase):
    def test_purposeful_headers_without_startup_warning_banners(self):
        for path in (
            "pages/3_Legal_Drafting.py",
            "pages/4_EU_Reporting.py",
            "pages/2_Communication_Studio.py",
            "pages/1_ToC_Builder.py",
            "writing_assistant.py",
        ):
            with self.subTest(page=path):
                app = AppTest.from_file(str(ROOT / path), default_timeout=25).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(
                    len(app.warning), 0,
                    "Initial page should not have repetitive warning banners",
                )
                self.assertLessEqual(len(app.info), 1)

    def test_chat_is_simple_without_dropping_input_screening(self):
        source = (ROOT / "pages/5_Chat_Workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Public or synthetic content only", source)
        self.assertNotIn("Sending a message shares it with Cloudflare", source)
        self.assertNotIn("Connection settings", source)
        self.assertIn("scan_text_fields(pending, public_legal=True)", source)
        self.assertIn("Attach a public document", source)
        self.assertIn("Move to project", source)
        self.assertIn("save_browser_history(", source)

    def test_critical_safety_logic_remains_in_place(self):
        pages = {
            "pages/3_Legal_Drafting.py": (
                "scan_text_fields(", "confirmed = st.checkbox(",
            ),
            "pages/4_EU_Reporting.py": (
                "scan_text_fields(", "confirm = st.checkbox(",
            ),
            "pages/2_Communication_Studio.py": (
                "scan_text_fields(", "safe = st.checkbox(",
            ),
            "pages/1_ToC_Builder.py": (
                "screen_upload(", "confirmed = st.checkbox(",
            ),
            "writing_assistant.py": (
                "scan_text(", "selected_public_attachment(",
            ),
            "review_ui.py": (
                "consent = st.checkbox(", "_confirmed_workers_free()",
            ),
        }
        for path, required in pages.items():
            with self.subTest(page=path):
                source = (ROOT / path).read_text(encoding="utf-8")
                for keyword in required:
                    self.assertIn(keyword, source)


if __name__ == "__main__":
    unittest.main()
