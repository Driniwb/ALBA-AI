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
        self.assertEqual(len(app.title), 0)
        self.assertFalse(any(
            "Browser saving unavailable" in str(item.value) for item in app.warning
        ))
        self.assertTrue(any("New chat" in str(item.label) for item in app.button))
        self.assertTrue(any(
            "Create project" in str(item.label) for item in app.button
        ))
        self.assertTrue(any("Projects" in str(h.value) for h in app.subheader))
        self.assertFalse(any("Assistant specialism" in str(item.label)
                             for item in app.selectbox))
        self.assertFalse(any("Connection settings" in str(item.label)
                             for item in app.expander))
        source = (ROOT / "pages" / "5_Chat_Workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('with st.popover(\n        "Preferences · " + current_country', source)
        self.assertIn('file_type=["docx", "xlsx", "pdf", "pptx"]', source)
        self.assertIn('key="alba_answer_style"', source)
        self.assertNotIn('with st.expander("Attach a public document (optional)")', source)

    def test_attachment_menu_has_only_office_pdf_formats(self):
        source = (ROOT / "pages" / "5_Chat_Workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('with st.popover(\n        "Preferences · " + current_country', source)
        self.assertNotIn('"https://chatgpt.com/"', source)
        self.assertNotIn('"https://claude.ai/"', source)
        self.assertNotIn('"https://gemini.google.com/"', source)
        self.assertIn('file_type=["docx", "xlsx", "pdf", "pptx"]', source)
        self.assertNotIn('st.title("ALBA")', source)
        self.assertNotIn('st.subheader("How can I help?")', source)
        self.assertNotIn('st.caption(chat_history_status(', source)
        self.assertIn('screen_upload(', source)
        self.assertIn('def _document_context(', source)
        self.assertNotIn('Ask ALBA a question', source)
        self.assertIn('"Message…"', source)
        self.assertIn('"Save project name"', source)
        self.assertIn('"Save chat name"', source)
        self.assertIn('"Move chat"', source)

    def test_sidebar_can_create_project_and_start_new_chat_in_it(self):
        class Response:
            status_code = 200
            def json(self):
                return {"success": True, "result": {
                    "response": "A synthetic project response."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"), default_timeout=25
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_TOKEN"
        app.run()
        self.assertEqual(len(app.exception), 0)
        app.text_input(key="alba_sidebar_project_name").set_value(
            "Chapter 14"
        ).run()
        app.button(key="alba_sidebar_create_project").click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(any(
            "Chapter 14" in e.label for e in app.expander
        ))
        projects = app.session_state["alba_demo_store"].list_projects(
            app.session_state["alba_demo_owner"]
        )
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0]["name"], "Chapter 14")
        self.assertEqual(
            app.session_state["alba_new_chat_project"], projects[0]["id"]
        )
        with patch("chat_backend.requests.post", return_value=Response()):
            app.chat_input[0].set_value(
                "Please review this synthetic public item."
            ).run()
        self.assertEqual(len(app.exception), 0)
        owner = app.session_state["alba_demo_owner"]
        chats = app.session_state["alba_demo_store"].list_conversations(owner)
        self.assertEqual(len(chats), 1)
        self.assertEqual(chats[0]["project_id"], projects[0]["id"])
        self.assertTrue(any(
            "Chapter 14" in e.label and "(1)" in e.label
            for e in app.expander
        ))

    def test_sidebar_project_and_chat_rename_then_move(self):
        class Response:
            status_code = 200
            def json(self):
                return {"success": True, "result": {
                    "response": "Synthetic public answer."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"), default_timeout=25
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_TOKEN"
        app.run()

        app.text_input(key="alba_sidebar_project_name").set_value("First project").run()
        app.button(key="alba_sidebar_create_project").click().run()
        owner = app.session_state["alba_demo_owner"]
        store = app.session_state["alba_demo_store"]
        project_id = store.list_projects(owner)[0]["id"]

        app.text_input(
            key="alba_project_rename_" + project_id
        ).set_value("Renamed project").run()
        app.button(
            key="alba_project_save_name_" + project_id
        ).click().run()
        self.assertEqual(store.list_projects(owner)[0]["name"], "Renamed project")

        with patch("chat_backend.requests.post", return_value=Response()):
            app.chat_input[0].set_value("Review a synthetic public rule.").run()
        chat_id = store.list_conversations(owner)[0]["id"]
        app.text_input(
            key="alba_sidebar_chat_name_" + chat_id
        ).set_value("Renamed conversation").run()
        app.button(
            key="alba_sidebar_save_name_" + chat_id
        ).click().run()
        self.assertEqual(
            store.get_conversation(owner, chat_id)["title"],
            "Renamed conversation",
        )

        destination = store.create_project(owner, "Destination project")
        app.run()
        app.selectbox(
            key="alba_sidebar_move_target_" + chat_id
        ).set_value(destination).run()
        app.button(
            key="alba_sidebar_move_chat_" + chat_id
        ).click().run()
        self.assertEqual(
            store.get_conversation(owner, chat_id)["project_id"], destination
        )
        self.assertEqual(len(app.exception), 0)

    def test_project_control_appears_only_in_existing_chat(self):
        class Response:
            status_code = 200

            def json(self):
                return {"success": True, "result": {
                    "response": "Synthetic source check completed."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "DEMO_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "DEMO_TOKEN"
        app.run()
        self.assertEqual(len(app.exception), 0)
        self.assertFalse(any(box.label == "Project" for box in app.selectbox))
        with patch("chat_backend.requests.post", return_value=Response()):
            app.chat_input[0].set_value("Analyse a synthetic public provision.").run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.chat_message), 2)
        self.assertTrue(any(box.label == "Project" for box in app.selectbox))
        source = (ROOT / "pages" / "5_Chat_Workspace.py").read_text(encoding="utf-8")
        self.assertIn('"Export conversation (.json)"', source)
        self.assertIn("st.download_button(", source)
        self.assertTrue(any("Delete conversation" in button.label for button in app.button))
        self.assertTrue(any("Save title" in button.label for button in app.button))
        # Restore is an action displayed only after a JSON file is uploaded.
        self.assertIn('"Restore conversation"', source)

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

    def test_new_chat_has_no_implicit_history_from_previous_chat(self):
        class Reply:
            status_code = 200
            def json(self):
                return {"success": True, "result": {
                    "response": "Synthetic public reply."
                }}

        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"),
            default_timeout=25,
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_TOKEN"
        app.run()
        seen = []
        def mock_post(url, **kwargs):
            seen.append(kwargs["json"]["messages"])
            return Reply()

        with patch("chat_backend.requests.post", side_effect=mock_post):
            app.chat_input[0].set_value("First independent public topic.").run()
            owner = app.session_state["alba_demo_owner"]
            store = app.session_state["alba_demo_store"]
            first_id = store.list_conversations(owner)[0]["id"]
            app.button(key="alba_new_chat").click().run()
            self.assertEqual(len(app.chat_message), 0)
            app.chat_input[0].set_value("Second independent public topic.").run()
            self.assertEqual(len(store.list_conversations(owner)), 2)
            self.assertNotIn("First independent public topic.",
                             str(seen[-1]))
            self.assertIn("Second independent public topic.",
                          str(seen[-1]))

            app.button(key="alba_open_" + first_id).click().run()
            app.chat_input[0].set_value("Continue the first public topic.").run()
            self.assertIn("First independent public topic.",
                          str(seen[-1]))
            self.assertNotIn("Second independent public topic.",
                             str(seen[-1]))
        self.assertEqual(len(app.exception), 0)

    def test_browser_autosave_runs_before_model_and_stages_prompt(self):
        source = (ROOT / "pages/5_Chat_Workspace.py").read_text(
            encoding="utf-8"
        )
        self.assertLess(
            source.index("browser_saved = save_browser_history("),
            source.index("with st.sidebar:"),
        )
        self.assertEqual(source.count("save_browser_history("), 1)
        self.assertIn('"alba_chat_submit_staged"', source)
        self.assertIn('"alba_browser_confirm_pending"', source)
        self.assertIn('"alba_browser_confirm_exchange"', source)
        self.assertIn('staged_submission = bool(', source)
        self.assertIn('st.stop()', source)
        self.assertLess(
            source.index("browser_saved = save_browser_history("),
            source.index("generate_chat_reply("),
        )

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
        self.assertNotIn("Sending a message shares it with Cloudflare", source)
        self.assertNotIn("Connection settings", source)
        self.assertIn('with st.popover(\n        "Preferences · " + current_country', source)
        self.assertIn("Move to project", source)
        # New Chat is centered; existing conversations use Streamlit's
        # native root-level, bottom-docked input.
        self.assertIn('with st.container(key="alba_chat_empty"):', source)
        self.assertIn('if conversation:\n    _chat_composer_controls()\n    submission = st.chat_input(', source)
        self.assertIn('key="alba_answer_style"', source)
        self.assertIn('key="alba_jurisdictions"', source)
        self.assertIn('with st.container(key="alba_chat_empty"):', source)
        self.assertIn('with st.popover("⋯", help="Chat options:', source)
        self.assertNotIn('st.subheader(conversation["title"])', source)
        self.assertNotIn('st.popover("Move to project"', source)


    def test_app_navigation_is_unified_without_legacy_pages(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("st.Page("), 1)
        self.assertIn('"pages/5_Chat_Workspace.py"', source)
        self.assertIn('position="hidden"', source)
        for other in (
            "writing_assistant.py",
            "pages/1_ToC_Builder.py",
            "pages/2_Communication_Studio.py",
            "pages/3_Legal_Drafting.py",
            "pages/4_EU_Reporting.py",
        ):
            self.assertNotIn(other, source)
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
        self.assertIn("initialize_browser_history(", source)
        self.assertIn("initialize_browser_history(", source)
        self.assertIn("save_browser_history(", source)
        self.assertNotIn("st.session_state.get('email')", source)


if __name__ == "__main__":
    unittest.main()
