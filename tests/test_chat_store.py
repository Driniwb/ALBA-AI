"""Offline chat persistence/isolation tests. All chat texts are synthetic."""
import tempfile
from pathlib import Path
import unittest

from chat_store import (
    ChatStore, MODES, owner_key_from_oidc, MAX_MESSAGE_CHARS,
)

ALICE = owner_key_from_oidc("https://issuer.example/", "synthetic-alice")
BOB = owner_key_from_oidc("https://issuer.example/", "synthetic-bob")


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.filename = str(Path(self.root.name) / "local_tests.sqlite3")
        self.store = ChatStore.sqlite_local(self.filename)

    def tearDown(self):
        self.root.cleanup()

    def test_oidc_claims_are_required_and_do_not_store_plain_identifier(self):
        self.assertEqual(len(ALICE), 64)
        self.assertNotIn("alice", ALICE)
        self.assertNotEqual(ALICE, BOB)
        self.assertNotEqual(ALICE, owner_key_from_oidc(
            "https://other-issuer.example/", "synthetic-alice"
        ))
        with self.assertRaises(ValueError):
            owner_key_from_oidc("", "someone")
        with self.assertRaises(ValueError):
            owner_key_from_oidc("issuer", "")

    def test_reopen_store_and_continue_saved_thread(self):
        project = self.store.create_project(ALICE, "Transport / Chapter 14")
        ident = self.store.create_conversation(
            ALICE, project_id=project, mode="legal", title="TDG Article 3"
        )
        self.store.append_exchange(
            ALICE, ident,
            "Compare Article 3 with the published directive.",
            "The annex reference needs review.",
        )
        self.assertEqual(len(self.store.list_messages(ALICE, ident)), 2)
        # Simulate a new login/server process: a new store instance reads disk.
        restarted = ChatStore.sqlite_local(self.filename)
        chat = restarted.get_conversation(ALICE, ident)
        self.assertEqual(chat["title"], "TDG Article 3")
        self.assertEqual(chat["project_id"], project)
        restarted.append_exchange(
            ALICE, ident, "What did we conclude?",
            "We flagged the annex reference for expert verification.",
        )
        transcript = self.store.list_messages(ALICE, ident)
        self.assertEqual([x["role"] for x in transcript],
                         ["user", "assistant", "user", "assistant"])
        self.assertIn("annex", transcript[-1]["content"])

    def test_different_users_never_read_modify_or_delete_anothers_chat(self):
        a_project = self.store.create_project(ALICE, "ALICE project")
        a_chat = self.store.create_conversation(
            ALICE, project_id=a_project, title="A private-by-owner chat"
        )
        self.store.append_exchange(
            ALICE, a_chat, "Public synthetic input", "Synthetic answer"
        )
        self.assertEqual(self.store.list_conversations(BOB), [])
        self.assertEqual(self.store.list_projects(BOB), [])
        self.assertIsNone(self.store.get_conversation(BOB, a_chat))
        self.assertEqual(self.store.list_messages(BOB, a_chat), [])
        self.assertFalse(self.store.rename_conversation(BOB, a_chat, "Stolen"))
        self.assertFalse(self.store.delete_conversation(BOB, a_chat))
        self.assertFalse(self.store.set_conversation_project(BOB, a_chat, None))
        self.assertFalse(self.store.delete_project(BOB, a_project))
        with self.assertRaises(ValueError):
            self.store.append_exchange(
                BOB, a_chat, "Attempt", "Should be rejected"
            )
        with self.assertRaises(ValueError):
            self.store.create_conversation(BOB, project_id=a_project)
        with self.assertRaises(ValueError):
            self.store.set_conversation_project(
                BOB, self.store.create_conversation(BOB),
                a_project,
            )
        self.assertIsNotNone(self.store.get_conversation(ALICE, a_chat))
        self.assertEqual(len(self.store.list_messages(ALICE, a_chat)), 2)

    def test_project_assignment_title_edit_and_deletion(self):
        first = self.store.create_project(ALICE, "EU reports")
        second = self.store.create_project(ALICE, "Legal drafting")
        chat = self.store.create_conversation(ALICE, mode="reporting", project_id=first)
        self.assertTrue(self.store.rename_project(ALICE, first, "EU reporting"))
        self.assertEqual(
            next(p["name"] for p in self.store.list_projects(ALICE)
                 if p["id"] == first),
            "EU reporting",
        )
        self.assertFalse(self.store.rename_project(BOB, first, "Hijacked"))
        self.assertFalse(self.store.rename_project(ALICE, "0" * 32, "No project"))
        self.assertTrue(self.store.rename_conversation(ALICE, chat, "Capacity Note"))
        self.assertTrue(self.store.set_conversation_project(ALICE, chat, second))
        self.assertTrue(self.store.delete_project(ALICE, second))
        self.assertIsNone(self.store.get_conversation(ALICE, chat)["project_id"])
        self.assertTrue(self.store.delete_conversation(ALICE, chat))
        self.assertIsNone(self.store.get_conversation(ALICE, chat))
        self.assertEqual(self.store.list_messages(ALICE, chat), [])

    def test_input_validation_and_transactions(self):
        with self.assertRaises(ValueError):
            self.store.create_project(ALICE, "")
        with self.assertRaises(ValueError):
            self.store.rename_project(ALICE, "not-a-valid-id", "Renamed")
        with self.assertRaises(ValueError):
            self.store.rename_project(ALICE, self.store.create_project(ALICE, "Temporary"), "")
        with self.assertRaises(ValueError):
            self.store.create_conversation(ALICE, mode="unknown")
        with self.assertRaises(ValueError):
            self.store.list_messages(ALICE, "not-a-valid-id")
        with self.assertRaises(ValueError):
            self.store.create_conversation("alice", title="Bad owner")
        chat = self.store.create_conversation(ALICE)
        for prompt, response in (
            ("", "output"),
            ("prompt", ""),
            ("x" * (MAX_MESSAGE_CHARS + 1), "output"),
        ):
            with self.subTest(length=len(prompt)):
                with self.assertRaises(ValueError):
                    self.store.append_exchange(ALICE, chat, prompt, response)
        self.assertEqual(self.store.list_messages(ALICE, chat), [])

    def test_demo_in_memory_databases_do_not_share_data(self):
        a = ChatStore.session_memory()
        b = ChatStore.session_memory()
        try:
            ident = a.create_conversation(ALICE, title="Temporary chat")
            a.append_exchange(ALICE, ident, "Question", "Answer")
            self.assertEqual(len(a.list_messages(ALICE, ident)), 2)
            self.assertEqual(b.list_conversations(ALICE), [])
            self.assertEqual(a.kind, "sqlite")
        finally:
            a.close()
            b.close()

    def test_only_postgresql_schemes_can_be_used_for_cloud(self):
        with self.assertRaises(ValueError):
            ChatStore.postgres("sqlite:///local.sqlite3")
        with self.assertRaises(ValueError):
            ChatStore.sqlite_local(":memory:")


if __name__ == "__main__":
    unittest.main()
