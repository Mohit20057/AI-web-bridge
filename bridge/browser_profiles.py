"""Discover named profiles in a Chromium browser's user-data directory."""

import json
import os
import sys
from pathlib import Path


def default_user_data_dir(browser_name: str) -> Path:
    """Return the standard Chrome or Edge user-data directory for this OS."""
    if sys.platform == "win32":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        vendor = "Google/Chrome" if browser_name == "chrome" else "Microsoft/Edge"
        return local_app_data / vendor / "User Data"
    if sys.platform == "darwin":
        vendor = "Google/Chrome" if browser_name == "chrome" else "Microsoft Edge"
        return Path.home() / "Library/Application Support" / vendor
    folder = "google-chrome" if browser_name == "chrome" else "microsoft-edge"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / folder


def list_browser_profiles(user_data_dir: Path) -> list[dict[str, str]]:
    """Read display names and directory IDs without exposing account emails."""
    local_state = user_data_dir / "Local State"
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    info = data.get("profile", {}).get("info_cache", {}) if isinstance(data, dict) else {}
    if not isinstance(info, dict):
        return []
    profiles = []
    for directory, details in info.items():
        if not isinstance(directory, str) or not isinstance(details, dict):
            continue
        profiles.append({"directory": directory, "name": str(details.get("name") or directory)})
    return sorted(profiles, key=lambda item: (item["name"].casefold(), item["directory"].casefold()))


def validate_profile_directory(directory: str) -> str:
    """Reject paths; the option accepts one Chromium profile folder name."""
    if not directory or directory in {".", ".."} or Path(directory).name != directory or "/" in directory or "\\" in directory:
        raise ValueError("Browser profile directory must be one folder name, such as 'Default' or 'Profile 1'.")
    return directory
