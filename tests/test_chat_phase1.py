"""Phase 1 chat history: explicit status, portable backup and safe mutations.

All test prompts are synthetic. Cloudflare is mocked; no credentials or real
conversation content leave this test process.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from chat_history_status import chat_history_status
from chat_backup import backup_bytes, parse_backup_file
from chat_store import ChatStore, owner_key_from_oidc
from guest_browser_storage import (
    export_guest_workspace, restore_guest_workspace,
)

ROOT = Path(__file__).resolve().parents[1]
OWNER1 = owner_key_from_oidc("https://synthetic.example", "owner-1")
OWNER2 = owner_key_from_oidc("https://synthetic.example", "owner-2")


class HistoryStatusTests(unittest.TestCase):
    def test_status_never_claims_account_sync_for_guest(self):
        self.assertIn("account", chat_history_status(account_saved=True))
        self.assertIn("this browser", chat_history_status(
            account_saved=False,
            browser_available=True, browser_confirmed=True,
        ))
        self.assertIn("Saving", chat_history_status(
            account_saved=False,
            browser_available=True, browser_confirmed=False,
        ))
        self.assertIn("Not saved", chat_history_status(
            account_saved=False,
            browser_available=False, browser_confirmed=False,
        ))
        self.assertIn("Not saved", chat_history_status(
            account_saved=False, browser_available=True,
            browser_confirmed=True, browser_error="Storage full.",
        ))


class HistoryBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = ChatStore.sqlite_local(
            str(Path(self.temp.name) / "chat_phase1.sqlite")
        )

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_portable_backup_and_restore_never_carry_user_identity(self):
        project = self.db.create_project(OWNER1, "Synthetic project")
        chat_id = self.db.create_conversation(
            OWNER1, mode="general", title="Synthetic first chat",
            project_id=project,
        )
        self.db.append_exchange(
            OWNER1, chat_id, "A synthetic public question.",
            "An illustrative public answer.",
        )
        backup = backup_bytes(
            self.db.get_conversation(OWNER1, chat_id),
            self.db.list_messages(OWNER1, chat_id),
        )
        self.assertNotIn(OWNER1.encode(), backup)
        self.assertNotIn(chat_id.encode(), backup)
        parsed = parse_backup_file(backup)
        new_chat = self.db.import_conversation_backup(OWNER2, parsed)
        self.assertEqual(
            len(self.db.list_messages(OWNER2, new_chat)), 2
        )
        self.assertIsNone(self.db.get_conversation(OWNER1, new_chat))
        self.assertIsNone(self.db.get_conversation(OWNER2, chat_id))

    def test_full_workspace_roundtrip_recovers_project_and_active_chat(self):
        project = self.db.create_project(OWNER1, "Chapter 14")
        chat_id = self.db.create_conversation(
            OWNER1, title="Public directive note", project_id=project,
        )
        self.db.append_exchange(
            OWNER1, chat_id, "A public synthetic directive question.",
            "The synthetic article requires a check.",
        )
        snapshot = export_guest_workspace(self.db, OWNER1, active_id=chat_id)
        other = ChatStore.session_memory()
        try:
            active = restore_guest_workspace(other, OWNER2, snapshot)
            self.assertEqual(len(other.list_projects(OWNER2)), 1)
            self.assertEqual(
                other.list_projects(OWNER2)[0]["name"], "Chapter 14"
            )
            self.assertEqual(
                other.get_conversation(OWNER2, active)["project_id"],
                other.list_projects(OWNER2)[0]["id"],
            )
        finally:
            other.close()

    def test_explicit_delete_is_owner_scoped(self):
        chat = self.db.create_conversation(OWNER1)
        self.db.append_exchange(OWNER1, chat, "Public question.", "Answer.")
        self.assertFalse(self.db.delete_conversation(OWNER2, chat))
        self.assertIsNotNone(self.db.get_conversation(OWNER1, chat))
        self.assertTrue(self.db.delete_conversation(OWNER1, chat))
        self.assertIsNone(self.db.get_conversation(OWNER1, chat))


class ChatManagementUiTests(unittest.TestCase):
    @staticmethod
    def _app():
        class Reply:
            status_code = 200

            def json(self):
                return {"success": True, "result": {
                    "response": "This synthetic public response is for testing."
                }}
        app = AppTest.from_file(
            str(ROOT / "pages" / "5_Chat_Workspace.py"), default_timeout=25
        )
        app.secrets["CLOUDFLARE_ACCOUNT_ID"] = "SYNTHETIC_ACCOUNT"
        app.secrets["CLOUDFLARE_API_TOKEN"] = "SYNTHETIC_TOKEN"
        app.run()
        assert len(app.exception) == 0
        with patch("chat_backend.requests.post", return_value=Reply()):
            app.chat_input[0].set_value(
                "Review the synthetic public legal note."
            ).run()
        assert len(app.exception) == 0
        return app

    def test_rename_then_confirmed_delete(self):
        app = self._app()
        owner = app.session_state["alba_demo_owner"]
        db = app.session_state["alba_demo_store"]
        chat_id = db.list_conversations(owner)[0]["id"]
        app.text_input(
            key="alba_rename_title_" + chat_id,
        ).set_value("A revised synthetic chat title").run()
        app.button(key="alba_save_title_" + chat_id).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            db.get_conversation(owner, chat_id)["title"],
            "A revised synthetic chat title",
        )
        self.assertTrue(
            app.button(key="alba_delete_chat_" + chat_id).disabled
        )
        app.checkbox(
            key="alba_delete_confirm_" + chat_id
        ).check().run()
        self.assertFalse(
            app.button(key="alba_delete_chat_" + chat_id).disabled
        )
        app.button(key="alba_delete_chat_" + chat_id).click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(db.list_conversations(owner), [])

    def test_account_login_not_advertised_without_cloud_database(self):
        app = self._app()
        self.assertTrue(any(
            "this browser" in str(i.value).casefold()
            for i in app.caption
        ))
        self.assertFalse(any(
            "Sign in to save conversations" in btn.label
            for btn in app.button
        ))


if __name__ == "__main__":
    unittest.main()
