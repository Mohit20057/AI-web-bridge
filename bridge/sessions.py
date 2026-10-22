"""Local, non-secret browser conversation metadata scoped to a project."""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class SessionStore:
    """Persist provider chat URLs without storing browser credentials or cookies."""

    def __init__(self, project_dir: Path | None = None, profile_scope: str | None = None):
        self.project_dir = (project_dir or Path.cwd()).resolve()
        self.project_id = hashlib.sha256(str(self.project_dir).encode("utf-8")).hexdigest()[:16]
        self.profile_scope_id = (
            hashlib.sha256(profile_scope.encode("utf-8")).hexdigest()[:12]
            if profile_scope
            else None
        )
        self.path = self.project_dir / ".ai-web-bridge" / "sessions.json"
        self.runs_path = self.project_dir / ".ai-web-bridge" / "runs.jsonl"

    def append_run(self, record: dict) -> None:
        """Append opt-in run metadata; callers must never pass prompt contents."""
        safe_record = {
            "version": 1,
            "project_id": self.project_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": record.get("provider"),
            "provider_name": record.get("provider_name"),
            "model": record.get("model"),
            "chat_url": self._safe_url(record.get("chat_url")),
            "prompt_ref": record.get("prompt_ref"),
            "context_ref": record.get("context_ref"),
            "output_ref": record.get("output_ref"),
        }
        self.runs_path.parent.mkdir(parents=True, exist_ok=True)
        with self.runs_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(safe_record, ensure_ascii=False) + "\n")

    def get_chat_url(self, provider: str) -> str | None:
        record = self._records().get(self._key(provider))
        if not isinstance(record, dict):
            return None
        value = record.get("last_chat_url")
        return value if isinstance(value, str) and value else None

    def save_chat_url(self, provider: str, url: str) -> None:
        # Keep only the origin and path. Query strings and fragments may contain
        # opaque application state and are not needed for conversation resume.
        safe_url = self._safe_url(url)
        records = self._records()
        records[self._key(provider)] = {
            "provider": provider,
            "project_id": self.project_id,
            "last_chat_url": safe_url,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="sessions-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"version": 1, "sessions": records}, stream, indent=2)
                stream.write("\n")
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def _records(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError):
            return {}
        records = data.get("sessions", {}) if isinstance(data, dict) else {}
        return records if isinstance(records, dict) else {}

    def _key(self, provider: str) -> str:
        scope = f":{self.profile_scope_id}" if self.profile_scope_id else ""
        return f"{provider}{scope}:{self.project_id}"

    @staticmethod
    def _safe_url(url: str | None) -> str | None:
        if not isinstance(url, str) or not url:
            return None
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return None
        hostname = parts.hostname
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        try:
            port = f":{parts.port}" if parts.port else ""
        except ValueError:
            return None
        return urlunsplit((parts.scheme, hostname + port, parts.path, "", ""))
