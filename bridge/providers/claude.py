"""Claude web UI adapter."""

from .selector_chat import SelectorChatProvider


class ClaudeProvider(SelectorChatProvider):
    """Uses Claude-specific URL and selectors from providers.json."""
