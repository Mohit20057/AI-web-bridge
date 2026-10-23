"""Chrome/Edge native-messaging process that relays extension requests locally."""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

from extension_bridge import MAX_MESSAGE_BYTES, extension_host_config_path


def _debug_log(event: str, detail: str = "") -> None:
    """Write temporary, content-free diagnostics for native-host startup issues."""
    try:
        path = Path.home() / ".ai-web-bridge" / "native_host_debug.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        with path.open("a", encoding="utf-8") as stream:
            stream.write(f"{timestamp} {event} {detail[:500]}\n")
    except OSError:
        pass


def _read_native_message() -> dict | None:
    stream = sys.stdin.buffer
    header = stream.read(4)
    if len(header) != 4:
        return None
    length = struct.unpack("=I", header)[0]
    if not 0 < length <= MAX_MESSAGE_BYTES:
        return None
    payload = stream.read(length)
    if len(payload) != length:
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_native_message(value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(payload) > MAX_MESSAGE_BYTES:
        payload = json.dumps({"ok": False, "error": "Native message exceeded the size limit."}).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("=I", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _read_line(stream) -> dict | None:
    line = stream.readline(MAX_MESSAGE_BYTES + 1)
    if not line or len(line) > MAX_MESSAGE_BYTES:
        return None
    try:
        value = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_line(connection: socket.socket, value: dict) -> None:
    data = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("Local message exceeded the size limit.")
    connection.sendall(data + b"\n")


def _extension_origin(argv: list[str]) -> str:
    return next((value for value in argv if value.startswith("chrome-extension://")), "")


def _load_config() -> dict:
    data = json.loads(extension_host_config_path().read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 1:
        raise RuntimeError("Native host setup is invalid. Rerun --extension-setup.")
    return data


def main() -> int:
    try:
        _debug_log("started", "args=" + repr(sys.argv[1:]))
        if sys.platform == "win32":
            import msvcrt

            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        config = _load_config()
        origin = _extension_origin(sys.argv[1:])
        if not origin or origin not in config.get("allowed_origins", []):
            raise RuntimeError("This extension is not registered with the AI Web Bridge native host.")
        message = _read_native_message()
        if not message:
            _debug_log("invalid_or_empty_native_message")
            return 1
        action = message.get("action")
        _debug_log("native_message_received", "action=" + str(action))
        port = int(message.get("port", config.get("port", 8765)))
        configured_port = int(config.get("port", 8765))
        if port != configured_port or not 1 <= port <= 65535:
            raise RuntimeError("The extension and local bridge ports do not match. Rerun setup with the selected port.")
        with socket.create_connection(("127.0.0.1", port), timeout=12) as connection:
            connection.settimeout(3600)
            reader = connection.makefile("rb")
            _write_line(connection, {"token": config["token"], "origin": origin})
            _write_line(connection, {
                "action": action,
                "port": port,
                "tab_url": str(message.get("tab_url", ""))[:4000],
                "result": message.get("result") if isinstance(message.get("result"), dict) else None,
            })
            reply = _read_line(reader)
            if reply is None:
                raise RuntimeError("The local bridge closed the connection without a reply.")
            _write_native_message(reply)
            _debug_log("bridge_reply_written", "action=" + str(action) + " ok=" + str(bool(reply.get("ok"))))
        return 0
    except Exception as exc:
        _debug_log("host_error", f"{type(exc).__name__}: {exc}")
        try:
            _write_native_message({"ok": False, "error": str(exc)[:2000]})
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
