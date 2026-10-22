"""Offline regression checks for context, configuration, sessions, and safety."""

import asyncio
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge"
sys.path.insert(0, str(BRIDGE))

# The CLI module imports Playwright at startup. Unit tests do not need a browser,
# so provide only the import symbol when the optional runtime dependency is absent.
try:
    import playwright.async_api  # noqa: F401
except ModuleNotFoundError:
    playwright = types.ModuleType("playwright")
    async_api = types.ModuleType("playwright.async_api")
    async_api.async_playwright = AsyncMock()
    playwright.async_api = async_api
    sys.modules["playwright"] = playwright
    sys.modules["playwright.async_api"] = async_api

from argon_bridge import (
    _build_comparison_prompt,
    _multi_output_path,
    _session_profile_scope,
    create_provider,
    execute_query,
)
from config import ConfigurationError, browser_settings, load_config
from context_packet import ContextPacketError, load_context_packet
from providers.base import ProviderError, validate_chat_url
from providers.chatgpt import ChatGPTProvider
from sessions import SessionStore


class ConfigurationTests(unittest.TestCase):
    def test_repo_provider_configuration_is_valid(self):
        config = load_config(BRIDGE / "providers.json")
        self.assertEqual(config["default_provider"], "gemini")
        self.assertEqual(set(config["providers"]), {"gemini", "chatgpt", "claude"})
        gemini_model_selector = config["providers"]["gemini"]["selectors"]["model_btn"]
        self.assertIn("bard-mode-menu-button", gemini_model_selector)
        self.assertNotIn("button[aria-haspopup='menu']", gemini_model_selector)
        for provider_id, provider_config in config["providers"].items():
            with self.subTest(provider=provider_id):
                self.assertEqual(create_provider(provider_id, provider_config).name, provider_config["name"])

    def test_non_object_configuration_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "providers.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "JSON object"):
                load_config(path)

    def test_browser_settings_rejects_invalid_port_and_browser(self):
        provider = load_config(BRIDGE / "providers.json")["providers"]["gemini"]
        import os

        original_browser = os.environ.get("BROWSER")
        original_port = os.environ.get("GEMINI_CDP_PORT")
        try:
            os.environ["BROWSER"] = "firefox"
            with self.assertRaisesRegex(ConfigurationError, "Unsupported BROWSER"):
                browser_settings(provider)
            os.environ["BROWSER"] = "chrome"
            os.environ["GEMINI_CDP_PORT"] = "70000"
            with self.assertRaisesRegex(ConfigurationError, "between 1 and 65535"):
                browser_settings(provider)
        finally:
            if original_browser is None:
                os.environ.pop("BROWSER", None)
            else:
                os.environ["BROWSER"] = original_browser
            if original_port is None:
                os.environ.pop("GEMINI_CDP_PORT", None)
            else:
                os.environ["GEMINI_CDP_PORT"] = original_port

    def test_default_chrome_keeps_legacy_scope_and_edge_gets_profile_scope(self):
        provider = load_config(BRIDGE / "providers.json")["providers"]["gemini"]
        chrome_profile = Path("~/ArgonChromeProfile").expanduser().resolve()
        edge_profile = Path("~/ArgonEdgeProfile").expanduser().resolve()
        self.assertIsNone(_session_profile_scope(provider, {
            "name": "chrome", "profile": chrome_profile,
        }))
        self.assertEqual(_session_profile_scope(provider, {
            "name": "edge", "profile": edge_profile,
        }), f"edge:{edge_profile}")


class ContextPacketTests(unittest.TestCase):
    def test_sensitive_paths_are_excluded_and_packet_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "context.json"
            path.write_text(json.dumps({
                "version": 1,
                "task": "Summarize this change",
                "files": [
                    {"path": ".env.local", "content": "SHOULD_NOT_APPEAR"},
                    {"path": "src/app.py", "content": "x" * 500},
                ],
            }), encoding="utf-8")
            rendered, notes = load_context_packet(path, max_chars=250)
            self.assertLessEqual(len(rendered), 250)
            self.assertNotIn("SHOULD_NOT_APPEAR", rendered)
            self.assertIn("TRUNCATED", rendered)
            self.assertTrue(any("sensitive-looking" in note for note in notes))

    def test_invalid_or_oversized_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "context.json"
            path.write_text(json.dumps({"version": 1, "task": "too large"}), encoding="utf-8")
            with self.assertRaises(ContextPacketError):
                load_context_packet(path, max_chars=4)


class SessionStoreTests(unittest.TestCase):
    def test_chat_urls_are_project_scoped_and_strip_query_and_fragment(self):
        with tempfile.TemporaryDirectory() as folder:
            first = SessionStore(Path(folder) / "one")
            second = SessionStore(Path(folder) / "two")
            first.save_chat_url("chatgpt", "https://chatgpt.com/c/123?secret=1#private")
            self.assertEqual(first.get_chat_url("chatgpt"), "https://chatgpt.com/c/123")
            self.assertIsNone(second.get_chat_url("chatgpt"))

    def test_chat_urls_are_isolated_between_browser_profiles(self):
        with tempfile.TemporaryDirectory() as folder:
            chrome = SessionStore(Path(folder), profile_scope="chrome:profile-a")
            edge = SessionStore(Path(folder), profile_scope="edge:profile-b")
            chrome.save_chat_url("gemini", "https://gemini.google.com/app/chrome-chat")
            edge.save_chat_url("gemini", "https://gemini.google.com/app/edge-chat")
            self.assertEqual(chrome.get_chat_url("gemini"), "https://gemini.google.com/app/chrome-chat")
            self.assertEqual(edge.get_chat_url("gemini"), "https://gemini.google.com/app/edge-chat")
            self.assertIsNone(SessionStore(Path(folder)).get_chat_url("gemini"))

    def test_run_log_never_serializes_prompt_or_response_contents(self):
        with tempfile.TemporaryDirectory() as folder:
            store = SessionStore(Path(folder))
            store.append_run({
                "provider": "gemini",
                "chat_url": "https://gemini.google.com/app/abc?token=private",
                "prompt_ref": "prompt-secret-marker",
                "context_ref": "context-file.json",
                "output_ref": "answer.md",
                "prompt": "must-not-be-recorded",
                "response": "also-must-not-be-recorded",
            })
            log = store.runs_path.read_text(encoding="utf-8")
            self.assertNotIn("must-not-be-recorded", log)
            self.assertNotIn("token=private", log)
            self.assertIn("prompt-secret-marker", log)


class ProviderSafetyTests(unittest.TestCase):
    def test_resume_url_must_be_https_on_configured_provider(self):
        self.assertEqual(
            validate_chat_url("https://chatgpt.com/c/123", "https://chatgpt.com/"),
            "https://chatgpt.com/c/123",
        )
        for url in (
            "http://chatgpt.com/c/123",
            "https://attacker.example/c/123",
            "https://chatgpt.com.attacker.example/c/123",
            "https://user@chatgpt.com/c/123",
            "https://chatgpt.com:8443/c/123",
        ):
            with self.subTest(url=url), self.assertRaises(ProviderError):
                validate_chat_url(url, "https://chatgpt.com/")

    def test_adapter_rejects_tampered_session_before_navigation(self):
        provider = ChatGPTProvider({
            "name": "ChatGPT",
            "url": "https://chatgpt.com/",
            "selectors": {},
        })

        class Context:
            pages = []

        with self.assertRaises(ProviderError):
            asyncio.run(provider.open_or_resume_chat(Context(), "https://attacker.example/"))


class DiagnosticScreenshotTests(unittest.TestCase):
    def _run_failed_query(self, diagnostics_dir):
        page = SimpleNamespace(screenshot=AsyncMock())
        context = SimpleNamespace(
            pages=[page],
            grant_permissions=AsyncMock(),
        )
        browser = SimpleNamespace(contexts=[context])
        chromium = SimpleNamespace(connect_over_cdp=AsyncMock(return_value=browser))
        # Python's async with protocol looks up methods on the manager's type.
        class PlaywrightManager:
            async def __aenter__(self):
                return SimpleNamespace(chromium=chromium)

            async def __aexit__(self, *_args):
                return None

        provider = SimpleNamespace(
            url="https://chatgpt.com/",
            name="ChatGPT",
            close=AsyncMock(),
            open_or_resume_chat=AsyncMock(return_value=page),
            wait_for_login=AsyncMock(),
            get_response_elements=AsyncMock(return_value=[]),
            send_prompt=AsyncMock(side_effect=RuntimeError("expected test failure")),
        )
        settings = {
            "host": "127.0.0.1",
            "port": 9223,
            "name": "chrome",
            "profile": Path("~/ArgonChromeProfile").expanduser(),
        }
        with (
            patch("argon_bridge.async_playwright", new=lambda: PlaywrightManager()),
            patch("argon_bridge.ensure_browser"),
            patch("argon_bridge.create_provider", return_value=provider),
            patch("argon_bridge.SessionStore") as session_store,
        ):
            session_store.return_value.get_chat_url.return_value = None
            with self.assertRaisesRegex(RuntimeError, "expected test failure"):
                asyncio.run(execute_query(
                    "prompt",
                    provider_id="chatgpt",
                    provider_config={
                        "browser": {"default_profile": "~/ArgonChromeProfile"},
                        "timeouts": {"login_seconds": 1},
                    },
                    connection_settings=settings,
                    diagnostics_dir=diagnostics_dir,
                ))
        return page

    def test_screenshots_are_disabled_by_default_and_opt_in(self):
        page = self._run_failed_query(None)
        page.screenshot.assert_not_awaited()
        with tempfile.TemporaryDirectory() as folder:
            page = self._run_failed_query(folder)
            page.screenshot.assert_awaited_once_with(path=str(Path(folder) / "debug_chatgpt.png"))


class ComparisonPromptTests(unittest.TestCase):
    def test_multi_provider_outputs_are_separate(self):
        base = _multi_output_path("review.md", "chatgpt")
        other = _multi_output_path("review.md", "claude")
        self.assertEqual(base.name, "review.chatgpt.response.md")
        self.assertNotEqual(base, other)

    def test_comparison_prompt_stays_within_budget_and_marks_truncation(self):
        rendered = _build_comparison_prompt(
            "task " * 200,
            [
                {"provider": "gemini", "response": "A" * 900},
                {"provider": "claude", "response": "B" * 900},
            ],
            max_chars=500,
        )
        self.assertLessEqual(len(rendered), 500)
        self.assertIn("Original context excerpt shortened", rendered)


if __name__ == "__main__":
    unittest.main()
