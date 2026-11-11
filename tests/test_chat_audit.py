"""Deeper audit: OIDC expiry, portable backups, owner isolation and DB security.

All fixtures use fictional public material and offline SQLite. No live secrets.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from chat_auth import verified_chat_owner
from chat_backup import (
    BACKUP_FORMAT, BACKUP_VERSION,
    backup_bytes, parse_backup_file, validate_backup,
)
from chat_store import ChatStore, owner_key_from_oidc


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ChatStore.sqlite_local(
            str(Path(self.temp.name) / "chat.sqlite3")
        )
        self.alice = owner_key_from_oidc("https://example.issuer", "alice")
        self.bob = owner_key_from_oidc("https://example.issuer", "bob")

    def tearDown(self):
        self.temp.cleanup()

    def _create_chat(self):
        cid = self.store.create_conversation(
            self.alice, title="Directive comparison", mode="legal"
        )
        self.store.append_exchange(
            self.alice, cid,
            "Check Article 3 of the synthetic public directive.",
            "The obligation and Annex II reference need verification.",
        )
        return cid

    def test_oidc_owner_uses_only_valid_unexpired_identity(self):
        claims = {
            "iss": "https://example.issuer",
            "sub": "alice", "iat": 100, "exp": 900,
        }
        self.assertEqual(
            verified_chat_owner(claims, now_seconds=200), self.alice
        )
        for changes in (
            {"exp": 199}, {"exp": None}, {"exp": "900"},
            {"iat": 300}, {"nbf": 300}, {"iss": ""},
            {"sub": ""}, {"exp": True},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    verified_chat_owner(
                        {**claims, **changes}, now_seconds=200
                    )

    def test_saved_chat_backup_restores_across_independent_store_sessions(self):
        cid = self._create_chat()
        source = self.store.get_conversation(self.alice, cid)
        raw = backup_bytes(
            source, self.store.list_messages(self.alice, cid)
        )
        self.assertIn(b"alba-chat-backup", raw)
        self.assertNotIn(self.alice.encode(), raw)
        self.assertNotIn(cid.encode(), raw)
        backup = parse_backup_file(raw)
        restored_store = ChatStore.sqlite_local(self.store.sqlite_file)
        restored = restored_store.import_conversation_backup(self.bob, backup)
        self.assertNotEqual(cid, restored)
        self.assertIsNone(restored_store.get_conversation(self.alice, restored))
        self.assertEqual(
            len(restored_store.list_messages(self.bob, restored)), 2
        )
        restored_store.append_exchange(
            self.bob, restored, "Continue this analysis.",
            "We previously flagged Annex II, and it remains unverified."
        )
        self.assertEqual(
            len(restored_store.list_messages(self.bob, restored)), 4
        )
        self.assertEqual(
            len(self.store.list_messages(self.alice, cid)), 2
        )

    def test_backup_rejects_private_data_and_incomplete_chat(self):
        payload = {
            "format": BACKUP_FORMAT, "version": BACKUP_VERSION,
            "title": "Public legal work", "mode": "legal",
            "messages": [
                {"role": "user", "content": "Check the public law."},
                {"role": "assistant", "content": "Please verify the text."},
            ]
        }
        valid = validate_backup(payload)
        self.assertEqual(len(valid["messages"]), 2)
        bad_samples = [
            {**payload, "messages": payload["messages"][:1]},
            {**payload, "messages": [
                {"role": "assistant", "content": "Wrong order"},
                {"role": "user", "content": "Wrong order"}]},
            {**payload, "messages": [
                {"role": "user", "content": "Email: user@example.org"},
                {"role": "assistant", "content": "Invalid"}]},
            {**payload, "title": "Email: private@example.org"},
            {**payload, "version": 300},
        ]
        for item in bad_samples:
            with self.subTest(kind=str(item)[:50]):
                with self.assertRaises(ValueError):
                    validate_backup(item)
        with self.assertRaises(ValueError):
            parse_backup_file(b"{invalid JSON]")
        with self.assertRaises(ValueError):
            parse_backup_file(b"")
        self.assertEqual(self.store.list_conversations(self.bob), [])

    def test_persistent_chat_metadata_refuses_private_identifiers(self):
        with self.assertRaises(ValueError):
            self.store.create_project(self.alice, "user@example.org")
        with self.assertRaises(ValueError):
            self.store.create_conversation(
                self.alice, title="Call +355 69 123 4567"
            )
        cid = self._create_chat()
        with self.assertRaises(ValueError):
            self.store.rename_conversation(
                self.alice, cid, "Email: person@example.org"
            )
        with self.assertRaises(ValueError):
            self.store.append_exchange(
                self.alice, cid, "Email: person@example.org", "Reply"
            )
        self.assertEqual(len(self.store.list_messages(self.alice, cid)), 2)

    def test_storage_healthcheck_and_tls_floor(self):
        self.assertTrue(self.store.healthcheck())
        mock_conn = self.store
        with patch.object(mock_conn, "_connect") as cm:
            cm.side_effect = RuntimeError("database unavailable")
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                mock_conn.healthcheck()

        for mode in ("disable", "allow", "prefer"):
            with self.subTest(mode=mode):
                # No external PostgreSQL connection is made.
                pg = ChatStore.__new__(ChatStore)
                pg.kind = "postgresql"
                pg.pg_dsn = (
                    "postgresql://test:password@localhost/none?sslmode=" + mode
                )
                with self.assertRaisesRegex(ValueError, "TLS-protected"):
                    with pg._connect():
                        pass

    def test_page_has_manual_import_and_never_silently_falls_back(self):
        src = (Path(__file__).resolve().parents[1] /
               "pages" / "5_Chat_Workspace.py").read_text(encoding="utf-8")
        self.assertIn("store.healthcheck()", src)
        self.assertIn("st.stop()", src)
        self.assertIn("verified_chat_owner(", src)
        # Backup format remains supported by the storage layer, but no
        # additional backup/import settings clutter the chat interface.
        self.assertNotIn("Restore conversation from backup", src)
        self.assertNotIn("Download resumable chat (.json)", src)
        self.assertIn("Move to project", src)
        self.assertIn("accept_file=True", src)
        self.assertIn('file_type=["docx", "xlsx", "pdf", "pptx"]', src)


if __name__ == "__main__":
    unittest.main()
