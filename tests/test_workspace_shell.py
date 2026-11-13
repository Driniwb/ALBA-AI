"""Static regression checks for the single ALBA 2.0 workspace shell."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceShellTests(unittest.TestCase):
    def test_modified_entrypoints_are_valid_python(self):
        for relative in (
            "app.py", "pages/5_Chat_Workspace.py",
            "alba_workspace_ui.py", "chat_backend.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(file=relative):
                compile(source, str(ROOT / relative), "exec")

    def test_only_projects_and_chats_are_sidebar_content_sections(self):
        chat = (ROOT / "pages/5_Chat_Workspace.py").read_text(encoding="utf-8")
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn('st.subheader("Projects")', chat)
        self.assertIn('st.subheader("Chats")', chat)
        self.assertIn('position="hidden"', app)
        self.assertEqual(app.count("st.Page("), 1)
        self.assertIn('"pages/5_Chat_Workspace.py"', app)
        for deprecated in (
            "ToC_Builder.py", "Legal_Drafting.py", "RIA_Builder.py",
            "EU_Reporting.py", "writing_assistant.py",
            "Communication_Studio.py",
        ):
            self.assertNotIn(deprecated, app)
        self.assertNotIn('key="alba_shortcut_toc"', chat)
        self.assertNotIn('key="alba_shortcut_legal_drafting"', chat)
        self.assertNotIn('key="alba_shortcut_reporting"', chat)
        self.assertNotIn("st.switch_page(", chat)
        self.assertNotIn('st.markdown("**Legal Assistant**")', chat)

    def test_native_attachment_and_closed_sources_panel(self):
        chat = (ROOT / "pages/5_Chat_Workspace.py").read_text(encoding="utf-8")
        self.assertIn("accept_file=True", chat)
        self.assertIn('file_type=["docx", "xlsx", "pdf", "pptx"]', chat)
        self.assertIn("screen_upload(", chat)
        self.assertIn('st.session_state.get("alba_sources_open", False)', chat)
        self.assertIn("list(submission.files)", chat)

    def test_workspace_visual_theme_has_light_background_and_accessible_ink(self):
        theme = (ROOT / "alba_workspace_ui.py").read_text(encoding="utf-8")
        self.assertIn("--alba-sidebar: #f5f7fb", theme)
        self.assertIn("--alba-ink: #1e293b", theme)
        self.assertIn("--alba-blue: #2d58a7", theme)


if __name__ == "__main__":
    unittest.main()
