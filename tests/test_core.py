import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import urllib.error

from flux.brain import build_context, reply
from flux.storage import Store


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "flux.db")

    def test_history_survives_restart_and_sessions_are_isolated(self):
        a, b = self.store.new_session(), self.store.new_session()
        self.store.save_turn(a, "Hello", "Hi")
        reopened = Store(self.store.path)
        self.assertEqual(reopened.messages(a)[1]["content"], "Hi")
        self.assertEqual(reopened.messages(b), [])

    def test_explicit_memory_deduplicates_and_forgets(self):
        self.store.remember("Tea")
        self.store.remember("Tea")
        self.assertEqual(len(self.store.memories()), 1)
        self.assertTrue(self.store.forget(self.store.memories()[0][0]))
        self.assertEqual(self.store.memories(), [])
        with self.assertRaises(ValueError):
            self.store.remember("x" * 301)

    def test_context_keeps_latest_complete_turns_under_budget(self):
        history = [{"role": role, "content": str(i) * 3000}
                   for i in range(3) for role in ("user", "assistant")]
        result = build_context(history, [(1, "Tea")], "Now")
        self.assertEqual(len(result), 6)
        self.assertEqual(result[1]["content"], "1" * 3000)
        self.assertIn("Tea", result[0]["content"])
        self.assertEqual(result[-1]["content"], "Now")

    @patch("flux.brain.urllib.request.build_opener")
    def test_ollama_request_and_response(self, factory):
        response = MagicMock()
        response.read.return_value = json.dumps({"message": {"content": "Hello"}})
        factory.return_value.open.return_value.__enter__.return_value = response
        self.assertEqual(reply([{"role": "user", "content": "Hi"}]), "Hello")
        request = factory.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertFalse(json.loads(request.data)["stream"])
        self.assertTrue(json.loads(request.data)["messages"][-2]["content"].endswith("/no_think"))
        self.assertEqual(json.loads(request.data)["messages"][-1]["content"], "<think>\n\n</think>\n\n")

    @patch("flux.brain.urllib.request.build_opener")
    def test_missing_model_has_actionable_error(self, factory):
        factory.return_value.open.side_effect = urllib.error.HTTPError("url", 404, "missing", {}, None)
        with self.assertRaisesRegex(RuntimeError, "ollama pull"):
            reply([])

    @patch("flux.brain.urllib.request.build_opener")
    def test_reasoning_prefix_is_not_shown_or_spoken(self, factory):
        response = MagicMock()
        response.read.return_value = json.dumps({"message": {"content": "Internal reasoning.</think>\nPython."}})
        factory.return_value.open.return_value.__enter__.return_value = response
        self.assertEqual(reply([]), "Python.")


if __name__ == "__main__":
    unittest.main()
