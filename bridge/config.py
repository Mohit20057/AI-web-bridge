"""Load and validate bridge provider configuration."""

import json
import os
from pathlib import Path
from typing import Any

from browser_profiles import default_user_data_dir


CONFIG_PATH = Path(__file__).resolve().with_name("providers.json")


class ConfigurationError(ValueError):
    """The provider configuration is missing or invalid."""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"Provider configuration not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Invalid JSON in provider configuration {path}: {exc}") from exc

    if not isinstance(config, dict):
        raise ConfigurationError("Provider configuration must be a JSON object.")
    providers = config.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise ConfigurationError("Provider configuration must define a non-empty 'providers' object.")
    default = config.get("default_provider")
    if default not in providers:
        raise ConfigurationError(f"Default provider '{default}' is not configured.")

    for provider_id, provider in providers.items():
        if not isinstance(provider, dict):
            raise ConfigurationError(f"Provider '{provider_id}' configuration must be an object.")
        for required in ("adapter", "name", "url", "browser", "selectors"):
            if required not in provider:
                raise ConfigurationError(f"Provider '{provider_id}' is missing required field '{required}'.")
        if not provider["adapter"].startswith("providers.") or ":" not in provider["adapter"]:
            raise ConfigurationError(
                f"Provider '{provider_id}' adapter must reference a class inside bridge/providers/."
            )
        browser = provider["browser"]
        if not isinstance(browser, dict):
            raise ConfigurationError(f"Provider '{provider_id}' browser configuration must be an object.")
        if not isinstance(provider["selectors"], dict):
            raise ConfigurationError(f"Provider '{provider_id}' selectors must be an object.")
        if browser.get("connection") != "cdp" or browser.get("engine") != "chromium":
            raise ConfigurationError(
                f"Provider '{provider_id}' uses an unsupported browser connection. "
                "This version supports Chromium over CDP."
            )
    return config


def browser_settings(provider: dict[str, Any]) -> dict[str, Any]:
    browser = provider["browser"]
    browser_name = os.environ.get("BROWSER", browser.get("default_browser", "chrome")).lower()
    if browser_name not in {"chrome", "edge"}:
        raise ConfigurationError(f"Unsupported BROWSER '{browser_name}'. Phase 2 supports chrome or edge.")
    profile_env = browser.get("edge_profile_env") if browser_name == "edge" else browser["profile_env"]
    profile_override = os.environ.get("BROWSER_PROFILE_DIR") or os.environ.get(profile_env)
    profile_directory = os.environ.get("BROWSER_PROFILE_NAME")
    if profile_directory and (
        profile_directory in {".", ".."}
        or Path(profile_directory).name != profile_directory
        or "/" in profile_directory
        or "\\" in profile_directory
    ):
        raise ConfigurationError("BROWSER_PROFILE_NAME must be one folder name, such as 'Default' or 'Profile 1'.")
    provider_port = os.environ.get(browser["port_env"])
    shared_profile = os.environ.get("BROWSER_PROFILE_DIR") or (profile_directory and not profile_override)
    if shared_profile:
        # A shared profile must use one shared browser endpoint to avoid
        # launching concurrent browser processes against the same profile.
        port_default = os.environ.get("CDP_PORT", "9222")
    elif provider_port:
        port_default = provider_port
    elif browser["port_env"] == "GEMINI_CDP_PORT":
        port_default = os.environ.get("CDP_PORT") or os.environ.get("CHROME_DEBUG_PORT") or str(browser["default_port"])
    else:
        port_default = str(browser["default_port"])
    try:
        port = int(port_default)
    except ValueError as exc:
        raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.") from exc
    if not 1 <= port <= 65535:
        raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.")
    host = os.environ.get("CDP_HOST", "127.0.0.1")
    default_profile = browser.get("default_profile", "~/ArgonChromeProfile")
    if browser_name == "edge":
        default_profile = browser.get("edge_default_profile", "~/ArgonEdgeProfile")
    profile_default = os.path.expanduser(default_profile)
    if profile_directory and not profile_override:
        profile_default = str(default_user_data_dir(browser_name))
    profile = Path(profile_override or profile_default).expanduser().resolve()
    executable = os.environ.get("BROWSER_EXE")
    connection_mode = os.environ.get("BROWSER_MODE", "managed").strip().lower()
    if connection_mode not in {"managed", "existing", "extension"}:
        raise ConfigurationError("BROWSER_MODE must be 'managed', 'existing', or 'extension'.")
    if connection_mode == "existing" and browser_name != "chrome":
        raise ConfigurationError(
            "BROWSER_MODE=existing currently supports Chrome only. Use --browser chrome or managed mode."
        )
    return {
        "name": browser_name,
        "mode": connection_mode,
        "host": host,
        "port": port,
        "profile": profile,
        "profile_directory": profile_directory,
        "executable": executable,
    }
