from pathlib import Path
import sqlite3
import tempfile
import unittest

from flux.storage import Store
from flux.memory import MemoryManager, extract_facts
from flux.conversation import ConversationManager


class MemoryConversationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "flux.db"
        self.store = Store(self.path)

    def test_preference_survives_restart_and_is_in_new_prompt(self):
        service = ConversationManager(self.store, lambda _: "Thanks for telling me.")
        service.send(self.store.new_session(), "My favorite programming language is Python.")
        reopened = Store(self.path)
        service = ConversationManager(reopened)
        messages = service.context(reopened.new_session(), "What programming language do I like?")
        self.assertIn("Python", messages[0]["content"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(reopened.memory_details()[0]["category"], "Preferences")

    def test_delete_is_persistent_and_preserves_other_chat_and_memory(self):
        a, b = self.store.new_session(), self.store.new_session()
        self.store.save_turn(a, "A", "Answer A")
        self.store.save_turn(b, "B", "Answer B")
        self.store.remember("My favorite language is Python.")
        self.store.rename_session(b, "Keep this")
        self.store.delete_session(a)
        reopened = Store(self.path)
        self.assertEqual(reopened.sessions(), [(b, "Keep this")])
        self.assertEqual(reopened.messages(a), [])
        self.assertEqual(len(reopened.messages(b)), 2)
        self.assertEqual(len(reopened.memories()), 1)
        reopened.delete_session(b)
        self.assertEqual(Store(self.path).sessions(), [])

    def test_relevance_correction_edit_delete_and_opt_out(self):
        memory = MemoryManager(self.store)
        memory.learn("My favorite programming language is Python.")
        memory.learn("My favorite programming language is Rust.")
        memory.learn("My favorite food is pasta.")
        self.assertEqual(len(self.store.memories()), 2)
        found = memory.retrieve("What programming language do I like?")
        self.assertEqual(len(found), 1)
        self.assertIn("Rust", found[0][1])
        memory.edit(found[0][0], "My favorite programming language is Go.", "Preferences")
        self.assertIn("Go", memory.retrieve("programming language")[0][1])
        self.store.forget(found[0][0])
        self.assertEqual(memory.retrieve("programming language"), [])
        self.store.set_setting("auto_memory", "false")
        memory.learn("My name is Sam.")
        self.assertEqual(len(self.store.memories()), 1)
        self.store.clear_memories()
        self.assertEqual(Store(self.path).memories(), [])

    def test_no_learning_from_quotes_questions_or_credentials(self):
        for text in ['"My name is Sam."', "My favorite language is Python?", "Imagine my name is Sam.", "My password is secret."]:
            self.assertEqual(extract_facts(text), [])

    def test_legacy_migration_preserves_ids_and_rows(self):
        legacy = Path(self.tmp.name) / "legacy.db"
        db = sqlite3.connect(legacy)
        db.executescript("""
            CREATE TABLE sessions(id TEXT PRIMARY KEY,title TEXT NOT NULL,created TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE messages(id INTEGER PRIMARY KEY,session TEXT,role TEXT,content TEXT,FOREIGN KEY(session) REFERENCES sessions(id));
            CREATE TABLE memories(id INTEGER PRIMARY KEY,content TEXT UNIQUE);
            INSERT INTO sessions(id,title) VALUES ('old','Existing');
            INSERT INTO messages(session,role,content) VALUES ('old','user','Hello');
            INSERT INTO memories(id,content) VALUES (7,'I prefer tea.');
        """)
        db.close()
        store = Store(legacy)
        self.assertEqual(store.memories(), [(7, "I prefer tea.")])
        self.assertEqual(store.messages("old")[0]["content"], "Hello")
        self.assertTrue(store.session_details()[0]["updated"])
        self.assertTrue(legacy.with_suffix(".before-v2.db").exists())
        self.assertEqual(Store(legacy).memories()[0][0], 7)

    def test_failure_does_not_save_turn_or_learn(self):
        def fail(_):
            raise RuntimeError("Offline")
        session = self.store.new_session()
        with self.assertRaises(RuntimeError):
            ConversationManager(self.store, fail).send(session, "My name is Sam.")
        self.assertEqual(self.store.messages(session), [])
        self.assertEqual(self.store.memories(), [])
