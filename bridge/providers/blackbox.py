"""Blackbox AI web UI adapter."""

from .selector_chat import SelectorChatProvider


class BlackboxProvider(SelectorChatProvider):
    """Uses Blackbox-specific URL and selectors from providers.json."""
