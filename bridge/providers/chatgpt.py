"""ChatGPT web UI adapter."""

from .selector_chat import SelectorChatProvider


class ChatGPTProvider(SelectorChatProvider):
    """Uses ChatGPT-specific URL and selectors from providers.json."""
