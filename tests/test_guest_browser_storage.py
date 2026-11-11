"""Public/synthetic-only same-browser workspace snapshots, no real browser."""
import json
import tempfile
import unittest
from pathlib import Path

from chat_store import ChatStore, owner_key_from_oidc
from guest_browser_storage import (
    WORKSPACE_FORMAT, WORKSPACE_VERSION, MAX_WORKSPACE_BYTES,
    export_guest_workspace, restore_guest_workspace,
    validate_guest_workspace,
)

OWNER1 = owner_key_from_oidc("https://synthetic", "first-user")
OWNER2 = owner_key_from_oidc("https://synthetic", "second-user")


class GuestBrowserStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = ChatStore.sqlite_local(str(Path(self.tmp.name) / "test.sqlite3"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_snapshot_round_trip_recovers_projects_chats_and_active_thread(self):
        project = self.db.create_project(OWNER1, "EU reports")
        chat = self.db.create_conversation(
            OWNER1, title="Transport acquis", mode="legal", project_id=project,
        )
        self.db.append_exchange(
            OWNER1, chat, "Compare a synthetic Article 3.",
            "Check the cited Annex II before transposition.",
        )
        payload = export_guest_workspace(
            self.db, OWNER1, active_id=chat,
        )
        self.assertLess(len(payload.encode()), MAX_WORKSPACE_BYTES)
        self.assertNotIn(OWNER1, payload)
        self.assertNotIn(chat, payload)
        self.assertEqual(validate_guest_workspace(payload)["active"], 0)

        new_db = ChatStore.session_memory()
        try:
            new_id = restore_guest_workspace(new_db, OWNER2, payload)
            self.assertIsNotNone(new_id)
            self.assertNotEqual(new_id, chat)
            self.assertEqual(len(new_db.list_projects(OWNER2)), 1)
            self.assertEqual(len(new_db.list_messages(OWNER2, new_id)), 2)
            self.assertIsNone(new_db.get_conversation(OWNER1, new_id))
            new_db.append_exchange(
                OWNER2, new_id, "Continue the legal review.",
                "Annex II still needs verification.",
            )
            self.assertEqual(len(new_db.list_messages(OWNER2, new_id)), 4)
        finally:
            new_db.close()

    def test_unanswered_question_survives_a_new_browser_session(self):
        project = self.db.create_project(OWNER1, "Legal drafting")
        chat = self.db.create_conversation(
            OWNER1, title="Legal review", project_id=project,
        )
        self.db.append_exchange(
            OWNER1, chat, "Check synthetic Article 4.",
            "Article 4 requires comparison with the annex.",
        )
        pending = "Please draft the next public provision."
        saved = export_guest_workspace(
            self.db, OWNER1, active_id=chat,
            pending_text=pending, pending_project_id=project,
        )
        clean = validate_guest_workspace(saved)
        self.assertEqual(clean["pending"], pending)
        self.assertEqual(clean["pending_project"], 0)
        restored = ChatStore.session_memory()
        try:
            restored_id = restore_guest_workspace(restored, OWNER2, saved)
            self.assertIsNotNone(restored_id)
            self.assertEqual(
                len(restored.list_messages(OWNER2, restored_id)), 2
            )
            self.assertEqual(
                restored.list_projects(OWNER2)[0]["name"], "Legal drafting"
            )
        finally:
            restored.close()

    def test_legacy_saved_workspace_without_pending_still_restores(self):
        original = json.loads(export_guest_workspace(self.db, OWNER1))
        original.pop("pending", None)
        original.pop("pending_project", None)
        self.assertIsNone(
            validate_guest_workspace(json.dumps(original))["pending"]
        )

    def test_sensitive_unanswered_questions_never_enter_browser_snapshots(self):
        with self.assertRaises(ValueError):
            export_guest_workspace(
                self.db, OWNER1,
                pending_text="Email: private.person@example.org",
            )
        original = json.loads(export_guest_workspace(self.db, OWNER1))
        original["pending"] = "Password: secretpassword"
        with self.assertRaises(ValueError):
            validate_guest_workspace(json.dumps(original))
        original["pending"] = "Public drafting question."
        original["pending_project"] = 99
        with self.assertRaises(ValueError):
            validate_guest_workspace(json.dumps(original))

    def test_js_component_is_registered_once_and_checks_read_back(self):
        from guest_browser_storage import _BROWSER_JS, _BROWSER_COMPONENT
        source = (
            Path(__file__).resolve().parents[1] /
            "guest_browser_storage.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(source.count("st.components.v2.component("), 1)
        self.assertIn("_BROWSER_COMPONENT = st.components.v2.component(", source)
        self.assertIn('setStateValue("saved", data.revision)', _BROWSER_JS)
        self.assertIn(
            "window.localStorage.getItem(key) !== data.payload", _BROWSER_JS
        )

    def test_empty_workspace_is_valid(self):
        raw = export_guest_workspace(self.db, OWNER1)
        result = validate_guest_workspace(raw)
        self.assertEqual(result["projects"], [])
        self.assertEqual(result["chats"], [])
        self.assertIsNone(result["active"])

    def test_broken_or_sensitive_browser_data_is_rejected(self):
        raw = export_guest_workspace(self.db, OWNER1)
        data = json.loads(raw)
        invalid = [
            "{not-json",
            json.dumps({**data, "version": 99}),
            json.dumps({**data, "projects": ["private.user@example.org"]}),
            json.dumps({**data, "active": 0}),
            json.dumps({**data, "chats": [{
                "project": -1,
                "chat": {"format": "alba-chat-backup", "version": 1,
                         "title": "Synthetic", "mode": "general",
                         "messages": [
                            {"role": "user", "content": "A"},
                            {"role": "assistant", "content": "B"}
                         ]}
            }]}),
        ]
        for item in invalid:
            with self.subTest(data=item[:45]):
                with self.assertRaises(ValueError):
                    validate_guest_workspace(item)
        with self.assertRaises(ValueError):
            validate_guest_workspace("X" * (MAX_WORKSPACE_BYTES + 1))

    def test_browser_restore_does_not_merge_into_existing_owner_data(self):
        first = self.db.create_conversation(OWNER1)
        self.db.append_exchange(OWNER1, first, "Question", "Response")
        snap = export_guest_workspace(self.db, OWNER1)
        with self.assertRaises(ValueError):
            restore_guest_workspace(self.db, OWNER1, snap)
        self.assertEqual(len(self.db.list_conversations(OWNER1)), 1)

    def test_client_script_uses_only_fixed_storage_key_no_executable_chat_text(self):
        from guest_browser_storage import _BROWSER_JS, BROWSER_KEY
        self.assertIn(BROWSER_KEY, _BROWSER_JS)
        self.assertIn("window.localStorage.getItem", _BROWSER_JS)
        self.assertIn("window.localStorage.setItem", _BROWSER_JS)
        self.assertNotIn("eval(", _BROWSER_JS)
        self.assertNotIn("innerHTML", _BROWSER_JS)


if __name__ == "__main__":
    unittest.main()
