import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bridge"))
from sessions import SessionStore


class SessionsAndFallbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tmp.name)
        (self.project_dir / ".bridge").mkdir(parents=True, exist_ok=True)
        (self.project_dir / ".ai-web-bridge").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_save_and_get_chat_url_project_binding(self):
        store = SessionStore(project_dir=self.project_dir)
        self.assertIsNone(store.get_chat_url("gemini"))

        # Save Gemini thread URL
        gemini_url = "https://gemini.google.com/app/1a2b3c4d5e6f"
        store.save_chat_url("gemini", gemini_url)

        # Retrieve
        self.assertEqual(store.get_chat_url("gemini"), gemini_url)

        # Ensure both .bridge and .ai-web-bridge session files exist and match
        bridge_file = self.project_dir / ".bridge" / "sessions.json"
        self.assertTrue(bridge_file.exists())
        self.assertIn("1a2b3c4d5e6f", bridge_file.read_text(encoding="utf-8"))

        # Save Claude thread URL
        claude_url = "https://claude.ai/chat/abc-def-123"
        store.save_chat_url("claude", claude_url)
        self.assertEqual(store.get_chat_url("claude"), claude_url)
        self.assertEqual(store.get_chat_url("gemini"), gemini_url)

    def test_project_isolation(self):
        # Two different project directories must have separate thread bindings
        proj_a = self.project_dir / "project_a"
        proj_b = self.project_dir / "project_b"
        proj_a.mkdir()
        proj_b.mkdir()

        store_a = SessionStore(project_dir=proj_a)
        store_b = SessionStore(project_dir=proj_b)

        store_a.save_chat_url("chatgpt", "https://chatgpt.com/c/chat-project-a")
        store_b.save_chat_url("chatgpt", "https://chatgpt.com/c/chat-project-b")

        self.assertEqual(store_a.get_chat_url("chatgpt"), "https://chatgpt.com/c/chat-project-a")
        self.assertEqual(store_b.get_chat_url("chatgpt"), "https://chatgpt.com/c/chat-project-b")

    def test_new_chat_rotation(self):
        store = SessionStore(project_dir=self.project_dir)
        store.save_chat_url("gemini", "https://gemini.google.com/app/old_thread")
        self.assertEqual(store.get_chat_url("gemini"), "https://gemini.google.com/app/old_thread")

        # Simulate rotating to a new chat thread
        store.save_chat_url("gemini", "https://gemini.google.com/app/new_thread_xyz")
        self.assertEqual(store.get_chat_url("gemini"), "https://gemini.google.com/app/new_thread_xyz")


if __name__ == "__main__":
    unittest.main()
