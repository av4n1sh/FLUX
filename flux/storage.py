"""SQLite persistence. Each operation owns its connection."""
import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .config import DATA

log = logging.getLogger(__name__)


class Store:
    def __init__(self, path=None):
        self.path = Path(path or DATA / "flux.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            with self.connect() as db:
                columns = [r[1] for r in db.execute("PRAGMA table_info(memories)")]
                if columns and "category" not in columns:
                    backup = self.path.with_suffix(".before-v2.db")
                    if not backup.exists():
                        target = sqlite3.connect(backup)
                        try:
                            db.backup(target)
                        finally:
                            target.close()
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL,
                    created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY, session TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL,
                    FOREIGN KEY(session) REFERENCES sessions(id));
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY, content TEXT NOT NULL UNIQUE);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)
            additions = {
                "sessions": {"updated": "TEXT NOT NULL DEFAULT ''"},
                "messages": {"created": "TEXT NOT NULL DEFAULT ''"},
                "memories": {"category": "TEXT NOT NULL DEFAULT 'Other'", "created": "TEXT NOT NULL DEFAULT ''",
                             "updated": "TEXT NOT NULL DEFAULT ''", "fact_key": "TEXT"},
            }
            for table, fields in additions.items():
                present = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
                for field, definition in fields.items():
                    if field not in present:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {field} {definition}")
            db.execute("UPDATE sessions SET updated=created WHERE updated=''")
            db.execute("UPDATE messages SET created=COALESCE((SELECT created FROM sessions WHERE id=messages.session),CURRENT_TIMESTAMP) WHERE created=''")
            db.execute("UPDATE memories SET created=CURRENT_TIMESTAMP WHERE created=''")
            db.execute("UPDATE memories SET updated=created WHERE updated=''")
            db.execute("CREATE INDEX IF NOT EXISTS messages_session ON messages(session,id)")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS memory_fact_key ON memories(fact_key) WHERE fact_key IS NOT NULL")
            db.execute("PRAGMA user_version=2")
        log.info("Memory database loaded; records=%d", len(self.memories()))

    @contextmanager
    def connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path)
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        except sqlite3.Error:
            log.error("Database operation failed", exc_info=False)
            raise
        finally:
            if db is not None:
                db.close()

    def new_session(self):
        identifier = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO sessions(id,title,updated) VALUES (?,?,CURRENT_TIMESTAMP)", (identifier, "New conversation"))
        return identifier

    def sessions(self):
        with self.connect() as db:
            return db.execute("SELECT id,title FROM sessions ORDER BY updated DESC,rowid DESC").fetchall()

    def session_details(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM sessions ORDER BY updated DESC,rowid DESC")]

    def rename_session(self, session, title):
        title = title.strip()
        if not title or len(title) > 100:
            raise ValueError("Use a conversation title between 1 and 100 characters.")
        with self.connect() as db:
            if not db.execute("UPDATE sessions SET title=?,updated=CURRENT_TIMESTAMP WHERE id=?", (title, session)).rowcount:
                raise ValueError("Conversation no longer exists.")

    def delete_session(self, session):
        with self.connect() as db:
            db.execute("DELETE FROM messages WHERE session=?", (session,))
            return db.execute("DELETE FROM sessions WHERE id=?", (session,)).rowcount > 0

    def messages(self, session, limit=None):
        with self.connect() as db:
            if limit is None:
                rows = db.execute("SELECT role,content FROM messages WHERE session=? ORDER BY id", (session,)).fetchall()
            else:
                rows = db.execute("SELECT role,content FROM messages WHERE session=? ORDER BY id DESC LIMIT ?", (session, limit)).fetchall()[::-1]
        return [dict(role=r, content=c) for r, c in rows]

    def save_turn(self, session, question, answer):
        with self.connect() as db:
            first = not db.execute("SELECT 1 FROM messages WHERE session=? LIMIT 1", (session,)).fetchone()
            db.executemany("INSERT INTO messages(session,role,content,created) VALUES (?,?,?,CURRENT_TIMESTAMP)", [(session, "user", question), (session, "assistant", answer)])
            if first:
                db.execute("UPDATE sessions SET title=? WHERE id=? AND title='New conversation'", (" ".join(question.split())[:55], session))
            db.execute("UPDATE sessions SET updated=CURRENT_TIMESTAMP WHERE id=?", (session,))

    def memories(self):
        with self.connect() as db:
            return db.execute("SELECT id,content FROM memories ORDER BY id").fetchall()

    def memory_details(self):
        with self.connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute("SELECT * FROM memories ORDER BY updated DESC,id DESC")]

    def remember(self, content, category="Other", fact_key=None):
        content = content.strip()
        if not content or len(content) > 300:
            raise ValueError("A memory must contain 1–300 characters.")
        with self.connect() as db:
            existing = db.execute("SELECT id FROM memories WHERE content=?", (content,)).fetchone()
            if existing:
                return existing[0]
            if fact_key:
                existing = db.execute("SELECT id FROM memories WHERE fact_key=?", (fact_key,)).fetchone()
                if existing:
                    db.execute("UPDATE memories SET content=?,category=?,updated=CURRENT_TIMESTAMP WHERE id=?", (content, category, existing[0]))
                    log.info("Memory updated; id=%s", existing[0])
                    return existing[0]
            if db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] >= 300:
                raise ValueError("Memory is full (300 facts). Remove a fact from Memory to make room.")
            cursor = db.execute("INSERT INTO memories(content,category,fact_key,created,updated) VALUES (?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)", (content, category, fact_key))
            identifier = cursor.lastrowid
        log.info("Memory saved; id=%s", identifier)
        return identifier

    def edit_memory(self, identifier, content, category="Other", fact_key=None):
        content = content.strip()
        if not content or len(content) > 300:
            raise ValueError("A memory must contain 1–300 characters.")
        with self.connect() as db:
            if not db.execute("UPDATE memories SET content=?,category=?,fact_key=?,updated=CURRENT_TIMESTAMP WHERE id=?", (content, category, fact_key, identifier)).rowcount:
                raise ValueError("Memory no longer exists.")
        log.info("Memory edited; id=%s", identifier)

    def clear_memories(self):
        with self.connect() as db:
            db.execute("DELETE FROM memories")
        log.info("Memories cleared")

    def setting(self, key, default=""):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def forget(self, identifier):
        with self.connect() as db:
            return db.execute("DELETE FROM memories WHERE id=?", (identifier,)).rowcount > 0
