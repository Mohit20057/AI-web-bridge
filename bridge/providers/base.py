"""Provider interface and shared, actionable bridge errors."""

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlsplit


class ProviderError(RuntimeError):
    """Base class for errors that can be explained to a bridge user."""


def validate_chat_url(chat_url: str | None, provider_url: str) -> str | None:
    """Accept stored conversation URLs only on the configured HTTPS provider site."""
    if not chat_url:
        return None
    candidate = urlsplit(chat_url)
    provider = urlsplit(provider_url)
    host = (candidate.hostname or "").casefold()
    provider_host = (provider.hostname or "").casefold()
    try:
        safe_port = candidate.port in (None, 443)
    except ValueError:
        safe_port = False
    if (
        candidate.scheme != "https"
        or not provider_host
        or not (host == provider_host or host.endswith("." + provider_host))
        or candidate.username is not None
        or candidate.password is not None
        or not safe_port
    ):
        raise ProviderError(
            "Stored conversation URL is not on the configured provider's HTTPS site. "
            "Remove the entry from .ai-web-bridge/sessions.json and retry."
        )
    return chat_url


class BrowserUnavailableError(ProviderError):
    """The configured browser endpoint could not be reached."""


class LoginRequiredError(ProviderError):
    """The provider's logged-in chat UI did not become available."""


class SelectorMismatchError(ProviderError):
    """The provider UI no longer matches the adapter's expected controls."""


class ModelUnavailableError(ProviderError):
    """A requested model was not available in the provider UI."""


class ResponseTimeoutError(ProviderError):
    """The provider did not finish generating before the timeout."""


class ResponseExtractionError(ProviderError):
    """The response was generated but could not be read from the provider UI."""


class ProviderAdapter(ABC):
    """Contract implemented by each browser-AI provider adapter."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = config["name"]
        self.url = config["url"]
        self.selectors = config["selectors"]

    @abstractmethod
    async def open_or_resume_chat(self, context, chat_url: str | None = None, new_chat: bool = False):
        """Open a provider page or resume the supplied conversation URL."""

    @abstractmethod
    async def wait_for_login(self, page, timeout: int = 120) -> None:
        """Wait until the signed-in provider input is ready."""

    @abstractmethod
    async def list_models(self, page) -> list[str]:
        """Return visible model choices, if the provider UI exposes them."""

    @abstractmethod
    async def select_model(self, page, model_name: str) -> str:
        """Select a model and return its visible label."""

    @abstractmethod
    async def send_prompt(self, page, prompt_text: str) -> None:
        """Submit a prompt through the provider's chat UI."""

    @abstractmethod
    async def get_response_elements(self, page):
        """Return the current provider response elements in page order."""

    @abstractmethod
    async def wait_for_response(self, page, initial_count: int = 0, timeout: int = 300) -> str:
        """Wait for a new response to finish and return its text."""

    async def close(self) -> None:
        """Release adapter-owned resources without closing the user's browser."""
