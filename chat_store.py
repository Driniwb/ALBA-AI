"""Framework-independent, owner-scoped conversation persistence for ALBA.

PostgreSQL is required for durable Cloud deployments. SQLite uses explicit
local-test or per-session memory modes only; never treat Community Cloud's
filesystem as durable. All lookups and writes enforce owner_key in SQL.
No raw user identifiers, email addresses or credentials are stored.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import re
import sqlite3
from urllib.parse import urlsplit, parse_qs
from typing import Iterator
from uuid import uuid4

MODES = {
    "general": "General legal and institutional assistant",
    "legal": "Legal Drafting & EU Acquis",
    "reporting": "EU Communication & Reporting",
    "communication": "Communication Studio",
}
_ID = re.compile(r"^[0-9a-f]{32}$")
_OWNER = re.compile(r"^[0-9a-f]{64}$")
MAX_MESSAGE_CHARS = 8500
MAX_PROJECT_NAME = 75
MAX_CHAT_TITLE = 90


def owner_key_from_oidc(issuer: str, subject: str) -> str:
    """Stable pseudonymous key based on provider issuer + verified OIDC subject."""
    if not isinstance(issuer, str) or not issuer.strip():
        raise ValueError("Verified issuer claim required for persisted conversations.")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("Verified subject claim required for persisted conversations.")
    return hashlib.sha256(
        (issuer.strip() + "\x00" + subject.strip()).encode("utf-8")
    ).hexdigest()


def _time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _check_owner(owner: str) -> None:
    if not isinstance(owner, str) or not _OWNER.fullmatch(owner):
        raise ValueError("Authenticated owner key required.")


def _check_id(value: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ValueError("Invalid resource identifier.")


class ChatStore:
    def __init__(self, *, pg_dsn: str = "", sqlite_file: str = "",
                 memory_uri: str = "") -> None:
        selected = sum(bool(x) for x in (pg_dsn, sqlite_file, memory_uri))
        if selected != 1:
            raise ValueError("Choose exactly one storage backend.")
        if pg_dsn:
            if not pg_dsn.startswith(("postgresql://", "postgres://")):
                raise ValueError("Only PostgreSQL connections are supported in Cloud.")
            self.kind = "postgresql"
        else:
            self.kind = "sqlite"
        self.pg_dsn = pg_dsn
        self.sqlite_file = sqlite_file
        self.memory_uri = memory_uri
        self._anchor = None
        if memory_uri:
            # Unique in-memory database per Streamlit browser session. It is NOT
            # persisted after the session ends, nor shared across sessions.
            self._anchor = sqlite3.connect(memory_uri, uri=True, timeout=10)
            self._anchor.execute("PRAGMA foreign_keys=ON")
        self.initialize()

    @classmethod
    def postgres(cls, dsn: str) -> "ChatStore":
        return cls(pg_dsn=dsn)

    @classmethod
    def sqlite_local(cls, filename: str) -> "ChatStore":
        """Local development/test only. Not a durable Community Cloud store."""
        if not filename or filename == ":memory:":
            raise ValueError("Use ChatStore.session_memory() for temporary chats.")
        return cls(sqlite_file=filename)

    @classmethod
    def session_memory(cls) -> "ChatStore":
        return cls(memory_uri=f"file:alba-session-{uuid4().hex}?mode=memory&cache=shared")

    def close(self) -> None:
        if self._anchor is not None:
            self._anchor.close()
            self._anchor = None

    @contextmanager
    def _connect(self) -> Iterator:
        if self.kind == "postgresql":
            import psycopg
            from psycopg.rows import dict_row
            # Do not silently permit plaintext PostgreSQL connections.
            # Preserve stronger provider settings (verify-full / verify-ca).
            sslmode = parse_qs(urlsplit(self.pg_dsn).query).get(
                "sslmode", ["require"]
            )[-1]
            if sslmode not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("A TLS-protected PostgreSQL connection is required.")
            conn = psycopg.connect(
                self.pg_dsn, connect_timeout=8, row_factory=dict_row,
                sslmode=sslmode,
            )
        else:
            conn = sqlite3.connect(
                self.memory_uri or self.sqlite_file,
                uri=bool(self.memory_uri),
                timeout=10,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _sql(self, query: str) -> str:
        return query.replace("?", "%s") if self.kind == "postgresql" else query

    def _execute(self, conn, query: str, args: tuple = ()):
        return conn.execute(self._sql(query), args)

    def healthcheck(self) -> bool:
        """Verify that the database is reachable before announcing Saved mode."""
        with self._connect() as db:
            row = self._execute(db, "SELECT 1 AS available").fetchone()
            return bool(row and row["available"] == 1)

    def initialize(self) -> None:
        message_pk = (
            "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
            if self.kind == "postgresql" else
            "INTEGER PRIMARY KEY AUTOINCREMENT"
        )
        with self._connect() as db:
            self._execute(db, """
                CREATE TABLE IF NOT EXISTS alba_projects (
                    id TEXT PRIMARY KEY,
                    owner_key TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self._execute(db, """
                CREATE TABLE IF NOT EXISTS alba_conversations (
                    id TEXT PRIMARY KEY,
                    owner_key TEXT NOT NULL,
                    project_id TEXT REFERENCES alba_projects(id)
                        ON DELETE SET NULL,
                    title TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self._execute(db, f"""
                CREATE TABLE IF NOT EXISTS alba_messages (
                    id {message_pk},
                    conversation_id TEXT NOT NULL
                        REFERENCES alba_conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            self._execute(db, """
                CREATE INDEX IF NOT EXISTS alba_chats_owner_updated
                ON alba_conversations(owner_key, updated_at)
            """)
            self._execute(db, """
                CREATE INDEX IF NOT EXISTS alba_projects_owner
                ON alba_projects(owner_key, created_at)
            """)
            self._execute(db, """
                CREATE INDEX IF NOT EXISTS alba_msgs_conversation
                ON alba_messages(conversation_id, id)
            """)

    def create_project(self, owner: str, name: str) -> str:
        _check_owner(owner)
        name = name.strip() if isinstance(name, str) else ""
        if not name or len(name) > MAX_PROJECT_NAME:
            raise ValueError("A project name of 1–75 characters is required.")
        ident = uuid4().hex
        with self._connect() as db:
            self._execute(db, """
                INSERT INTO alba_projects(id, owner_key, name, created_at)
                VALUES (?, ?, ?, ?)
            """, (ident, owner, name, _time()))
        return ident

    def list_projects(self, owner: str) -> list[dict]:
        _check_owner(owner)
        with self._connect() as db:
            rows = self._execute(db, """
                SELECT id, name, created_at FROM alba_projects
                WHERE owner_key = ? ORDER BY created_at, id
            """, (owner,)).fetchall()
        return [dict(row) for row in rows]

    def delete_project(self, owner: str, project_id: str) -> bool:
        _check_owner(owner)
        _check_id(project_id)
        with self._connect() as db:
            self._execute(db, """
                UPDATE alba_conversations SET project_id = NULL
                WHERE owner_key = ? AND project_id = ?
            """, (owner, project_id))
            cursor = self._execute(db, """
                DELETE FROM alba_projects WHERE owner_key = ? AND id = ?
            """, (owner, project_id))
            return cursor.rowcount == 1

    def _owns_project(self, db, owner: str, project_id: str) -> bool:
        _check_id(project_id)
        return self._execute(db, """
            SELECT id FROM alba_projects WHERE id = ? AND owner_key = ?
        """, (project_id, owner)).fetchone() is not None

    def create_conversation(self, owner: str, *, mode: str = "general",
                            project_id: str | None = None,
                            title: str = "New chat") -> str:
        _check_owner(owner)
        if mode not in MODES:
            raise ValueError("Unsupported conversation type.")
        title = title.strip() if isinstance(title, str) else ""
        if not title or len(title) > MAX_CHAT_TITLE:
            raise ValueError("Invalid conversation title.")
        ident, now = uuid4().hex, _time()
        with self._connect() as db:
            if project_id is not None and not self._owns_project(db, owner, project_id):
                raise ValueError("Project not available for this user.")
            self._execute(db, """
                INSERT INTO alba_conversations
                (id, owner_key, project_id, title, mode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ident, owner, project_id, title, mode, now, now))
        return ident

    def list_conversations(self, owner: str) -> list[dict]:
        _check_owner(owner)
        with self._connect() as db:
            rows = self._execute(db, """
                SELECT id, project_id, title, mode, created_at, updated_at
                FROM alba_conversations WHERE owner_key = ?
                ORDER BY updated_at DESC, id DESC
            """, (owner,)).fetchall()
        return [dict(row) for row in rows]

    def get_conversation(self, owner: str, conversation_id: str) -> dict | None:
        _check_owner(owner)
        _check_id(conversation_id)
        with self._connect() as db:
            row = self._execute(db, """
                SELECT id, project_id, title, mode, created_at, updated_at
                FROM alba_conversations WHERE owner_key = ? AND id = ?
            """, (owner, conversation_id)).fetchone()
        return dict(row) if row else None

    def rename_conversation(self, owner: str, conversation_id: str, title: str) -> bool:
        _check_owner(owner)
        _check_id(conversation_id)
        title = title.strip() if isinstance(title, str) else ""
        if not title or len(title) > MAX_CHAT_TITLE:
            raise ValueError("Invalid conversation title.")
        with self._connect() as db:
            cur = self._execute(db, """
                UPDATE alba_conversations SET title = ?, updated_at = ?
                WHERE id = ? AND owner_key = ?
            """, (title, _time(), conversation_id, owner))
            return cur.rowcount == 1

    def set_conversation_project(
        self, owner: str, conversation_id: str, project_id: str | None
    ) -> bool:
        _check_owner(owner)
        _check_id(conversation_id)
        with self._connect() as db:
            if project_id is not None and not self._owns_project(db, owner, project_id):
                raise ValueError("Project not available for this user.")
            cur = self._execute(db, """
                UPDATE alba_conversations SET project_id = ?, updated_at = ?
                WHERE id = ? AND owner_key = ?
            """, (project_id, _time(), conversation_id, owner))
            return cur.rowcount == 1

    def delete_conversation(self, owner: str, conversation_id: str) -> bool:
        _check_owner(owner)
        _check_id(conversation_id)
        with self._connect() as db:
            cur = self._execute(db, """
                DELETE FROM alba_conversations WHERE id = ? AND owner_key = ?
            """, (conversation_id, owner))
            return cur.rowcount == 1

    def list_messages(self, owner: str, conversation_id: str) -> list[dict]:
        _check_owner(owner)
        _check_id(conversation_id)
        with self._connect() as db:
            rows = self._execute(db, """
                SELECT m.role, m.content, m.created_at
                FROM alba_messages AS m
                JOIN alba_conversations AS c ON c.id = m.conversation_id
                WHERE c.id = ? AND c.owner_key = ?
                ORDER BY m.id ASC
            """, (conversation_id, owner)).fetchall()
        return [dict(row) for row in rows]

    def append_exchange(self, owner: str, conversation_id: str,
                        user_text: str, assistant_text: str) -> None:
        """Save both turns as one transaction; foreign user chat stays invisible."""
        _check_owner(owner)
        _check_id(conversation_id)
        for content in (user_text, assistant_text):
            if (not isinstance(content, str) or not content.strip()
                    or len(content) > MAX_MESSAGE_CHARS):
                raise ValueError("Chat messages must be 1–8,500 characters.")
        with self._connect() as db:
            owned = self._execute(db, """
                SELECT id FROM alba_conversations
                WHERE id = ? AND owner_key = ?
            """, (conversation_id, owner)).fetchone()
            if owned is None:
                raise ValueError("Conversation not accessible.")
            now = _time()
            for role, body in (("user", user_text), ("assistant", assistant_text)):
                self._execute(db, """
                    INSERT INTO alba_messages(conversation_id, role, content, created_at)
                    VALUES (?, ?, ?, ?)
                """, (conversation_id, role, body, now))
            self._execute(db, """
                UPDATE alba_conversations SET updated_at = ?
                WHERE id = ? AND owner_key = ?
            """, (now, conversation_id, owner))
