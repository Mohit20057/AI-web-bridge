"""Validate, filter, and render compact project context packets."""

import json
from pathlib import Path
from typing import Any


DEFAULT_CONTEXT_LIMIT_CHARS = 24_000
ALLOWED_FIELDS = {
    "version",
    "task",
    "project_summary",
    "recent_changes",
    "files",
    "errors",
    "constraints",
    "requested_output",
}
SENSITIVE_EXTENSIONS = {".key", ".pem", ".p12", ".pfx", ".p8"}
SENSITIVE_NAMES = {
    ".env",
    "id_rsa",
    "id_ed25519",
    "credentials.json",
    "mcp_config.json",
}
SENSITIVE_WORDS = ("secret", "credential", "password", "private-key", "token")


class ContextPacketError(ValueError):
    """The context packet is invalid or cannot fit within its size budget."""


def _is_sensitive_path(path: str) -> bool:
    normalized = path.replace("\\", "/").strip("/")
    parts = [part.casefold() for part in normalized.split("/") if part]
    if not parts:
        return True
    name = parts[-1]
    if name == ".env.example":
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name in SENSITIVE_NAMES or Path(name).suffix.casefold() in SENSITIVE_EXTENSIONS:
        return True
    if any(word in name for word in SENSITIVE_WORDS):
        return True
    return any(part in {".ssh", "secrets", "credentials", "private_keys"} for part in parts[:-1])


def load_context_packet(
    path: Path,
    max_chars: int = DEFAULT_CONTEXT_LIMIT_CHARS,
    handoff: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """Return a bounded Markdown context and non-secret filtering/truncation notes."""
    if max_chars < 1:
        raise ContextPacketError("Context character limit must be greater than zero.")
    try:
        packet: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContextPacketError(f"Context packet not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContextPacketError(f"Could not read a valid UTF-8 JSON context packet: {exc}") from exc

    if not isinstance(packet, dict):
        raise ContextPacketError("Context packet must be a JSON object.")
    unknown = sorted(set(packet) - ALLOWED_FIELDS)
    if unknown:
        raise ContextPacketError("Unknown context packet field(s): " + ", ".join(unknown))
    if isinstance(packet.get("version"), bool) or packet.get("version") != 1:
        raise ContextPacketError("Context packet version must be 1.")
    if not isinstance(packet.get("task"), str) or not packet["task"].strip():
        raise ContextPacketError("Context packet requires a non-empty 'task' string.")

    for field in ("project_summary", "recent_changes", "requested_output"):
        if field in packet and not isinstance(packet[field], str):
            raise ContextPacketError(f"Context packet field '{field}' must be a string.")
    for field in ("errors", "constraints"):
        if field in packet and (
            not isinstance(packet[field], list)
            or any(not isinstance(item, str) for item in packet[field])
        ):
            raise ContextPacketError(f"Context packet field '{field}' must be a list of strings.")

    carried_fields = []
    previous_task = None
    if isinstance(handoff, dict):
        saved_task = handoff.get("task")
        if isinstance(saved_task, str) and saved_task.strip() != packet["task"].strip():
            previous_task = saved_task.strip()
        for field in ("project_summary", "recent_changes"):
            if not packet.get(field) and isinstance(handoff.get(field), str) and handoff[field].strip():
                packet[field] = handoff[field]
                carried_fields.append(field)

    files = packet.get("files", [])
    if not isinstance(files, list):
        raise ContextPacketError("Context packet field 'files' must be a list.")
    clean_files: list[tuple[str, str]] = []
    excluded = 0
    for index, item in enumerate(files):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("content"), str):
            raise ContextPacketError(f"Context packet file entry {index} requires string 'path' and 'content' fields.")
        file_path = item["path"].strip()
        if not file_path:
            raise ContextPacketError(f"Context packet file entry {index} has an empty path.")
        if _is_sensitive_path(file_path):
            excluded += 1
            continue
        clean_files.append((file_path, item["content"]))

    sections = ["# Task context", "## Task", packet["task"].strip()]
    if previous_task:
        sections.extend(("## Previous task", previous_task))
    for field, title in (
        ("project_summary", "Project summary"),
        ("recent_changes", "Recent changes"),
    ):
        value = packet.get(field, "").strip()
        if value:
            sections.extend((f"## {title}", value))
    for field, title in (("errors", "Relevant errors"), ("constraints", "Constraints")):
        values = [value.strip() for value in packet.get(field, []) if value.strip()]
        if values:
            sections.extend((f"## {title}", "\n".join(f"- {value}" for value in values)))
    requested_output = packet.get("requested_output", "").strip()
    if requested_output:
        sections.extend(("## Requested output", requested_output))

    fixed_text = "\n\n".join(sections)
    if len(fixed_text) > max_chars:
        raise ContextPacketError(
            f"Task summary and instructions alone exceed the {max_chars:,}-character context limit. "
            "Shorten the packet's summary, errors, constraints, or requested output."
        )

    notes = []
    if carried_fields:
        notes.append("Carried forward saved project handoff: " + ", ".join(carried_fields) + ".")
    if excluded:
        notes.append(f"Excluded {excluded} file(s) with sensitive-looking paths.")
    files_heading = "\n\n## Relevant files\n\n"
    remaining = max_chars - len(fixed_text) - len(files_heading)
    rendered_files: list[str] = []
    truncated = False
    omitted = 0
    for index, (file_path, content) in enumerate(clean_files):
        separator = 2 if rendered_files else 0
        header = f"### File: {file_path}\n\n"
        available = remaining - separator
        if available < len(header):
            omitted = len(clean_files) - index
            break
        content_budget = available - len(header)
        if len(content) <= content_budget:
            rendered = header + content
            rendered_files.append(rendered)
            remaining -= separator + len(rendered)
            continue

        marker = "\n\n[TRUNCATED at context size limit]"
        snippet_budget = content_budget - len(marker)
        if snippet_budget >= 0:
            rendered_files.append(header + content[:snippet_budget] + marker)
        else:
            omitted = len(clean_files) - index
        truncated = True
        break

    if rendered_files:
        rendered = fixed_text + files_heading + "\n\n".join(rendered_files)
    else:
        rendered = fixed_text
    if omitted:
        notes.append(f"Omitted {omitted} file(s) at the context size limit.")
    if truncated:
        notes.append(f"Context was limited to {max_chars:,} characters; some file content may be truncated or omitted.")
    return rendered, notes
