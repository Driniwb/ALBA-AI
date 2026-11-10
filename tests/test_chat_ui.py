"""Streamlit chat workspace smoke tests without credentials or external calls."""
import unittest
from pathlib import Path

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
            "Temporary workspace" in str(item.value) for item in app.info
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
        self.assertIn("will disappear after refresh/restart", source)
        self.assertNotIn("st.session_state.get('email')", source)


if __name__ == "__main__":
    unittest.main()
