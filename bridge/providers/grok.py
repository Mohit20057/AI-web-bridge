"""Grok (xAI) web UI adapter."""

from .selector_chat import SelectorChatProvider


class GrokProvider(SelectorChatProvider):
    """Uses Grok-specific URL and selectors from providers.json."""
