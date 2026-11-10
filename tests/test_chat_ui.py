"""Streamlit chat workspace smoke tests without credentials or external calls."""
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

class ChatWorkspaceUITests(unittest.TestCase):
    def test_chat_workspace_loads_as_temporary_demo_without_auth(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any("Chat Workspace" in item.value for item in app.title))
        self.assertTrue(any(
            "Browser saving unavailable" in str(item.value) for item in app.warning
        ))
        self.assertTrue(any("New chat" in str(item.label) for item in app.button))
        self.assertTrue(any("Create project" in str(item.label) for item in app.button))
        self.assertTrue(any("Assistant specialism" in str(item.label)
                            for item in app.selectbox))

    def test_guest_can_create_project_without_a_database_or_login(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        ).run()
        self.assertEqual(len(app.exception), 0)
        name = next(item for item in app.text_input
                    if item.label == "New project")
        name.set_value("Synthetic EU transport").run()
        submit = next(button for button in app.button
                      if button.label == "Create project")
        submit.click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("Synthetic EU transport", [
            str(option) for box in app.selectbox for option in box.options
        ])

    def test_real_chat_widget_flow_uses_previous_turns_and_can_reopen(self):
        """Exercise Streamlit's chat_input, not only a static page render."""
        class Generated:
            status_code = 200

            def json(self):
                return {
                    "success": True,
                    "result": {"response": "Annex II requires expert verification."},
                }

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "DEMO_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "DEMO_TOKEN"
        app.run()
        self.assertEqual(len(app.exception), 0)
        calls = []
        def mock_post(url, **kwargs):
            calls.append(kwargs["json"]["messages"])
            return Generated()

        with patch("chat_backend.requests.post", side_effect=mock_post):
            app.chat_input[0].set_value("Check Annex II.").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), 2)
            app.chat_input[0].set_value("Continue that source check.").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), 4)
            self.assertEqual(calls[1][-1]["content"], "Continue that source check.")
            self.assertTrue(any(
                "Check Annex II." == m["content"] for m in calls[1]
            ))
            app.button(key="alba_new_chat").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), 0)
            open_chat = next(
                x for x in app.button if str(x.key).startswith("alba_open_")
            )
            open_chat.click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.chat_message), 4)

    def test_failed_question_is_kept_and_retried_successfully(self):
        class RateLimited:
            status_code = 429
        class GoodReply:
            status_code = 200
            def json(self):
                return {"success": True, "result": {
                    "response": "The synthetic report needs expert verification."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_KEY"
        app.run()
        self.assertEqual(len(app.exception), 0)
        
        calls = []
        def rate_limit_post(url, **kwargs):
            calls.append(url)
            return RateLimited()
        with patch("chat_backend.requests.post", side_effect=rate_limit_post):
            app.chat_input[0].set_value(
                "Please check the synthetic capacity note."
            ).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            app.session_state["alba_pending_chat_text"],
            "Please check the synthetic capacity note.",
        )
        self.assertTrue(any("429" in str(err.value) for err in app.error))
        self.assertTrue(any(
            button.label == "Retry this question" for button in app.button
        ))

        with patch("chat_backend.requests.post", return_value=GoodReply()):
            app.button(key="alba_retry_chat").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.chat_message), 2)
        self.assertIsNone(app.session_state["alba_pending_chat_text"])

    def test_composer_is_ready_without_a_separate_consent_checkbox(self):
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_KEY"
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(app.chat_input[0].disabled)
        self.assertFalse(any(
            check.key == "alba_chat_public_confirm" for check in app.checkbox
        ))
        source = (ROOT / "pages" / "5_Chat_Workspace.py").read_text(encoding="utf-8")
        self.assertIn("Sending a message shares it with Cloudflare", source)


    def test_app_navigation_includes_workspace_as_default_and_legacy_pages(self):
        text = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('"pages/5_Chat_Workspace.py"', text)
        self.assertIn('title="Chat Workspace"', text)
        for other in (
            "writing_assistant.py",
            "pages/1_ToC_Builder.py",
            "pages/2_Communication_Studio.py",
            "pages/3_Legal_Drafting.py",
            "pages/4_EU_Reporting.py",
        ):
            self.assertIn(other, text)
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=25).run()
        self.assertEqual(len(app.exception), 0)

    def test_persistence_requires_both_authentication_and_external_database(self):
        source = (ROOT / "pages" / "5_Chat_Workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("_verified_owner() if _oidc_configured() else None", source)
        self.assertIn("if owner and dsn:", source)
        self.assertIn("ChatStore.postgres(dsn)", source)
        self.assertIn("ChatStore.session_memory()", source)
        self.assertIn("History saved in this browser only", source)
        self.assertIn("initialize_browser_history(", source)
        self.assertIn("save_browser_history(", source)
        self.assertNotIn("st.session_state.get('email')", source)


if __name__ == "__main__":
    unittest.main()
