"""Loopback broker and native-host registration for the browser extension."""

from __future__ import annotations

import json
import secrets
import socket
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEFAULT_EXTENSION_PORT = 8765
HOST_NAME = "com.ai_web_bridge.native"
MAX_MESSAGE_BYTES = 1_000_000


def config_dir() -> Path:
    return Path.home() / ".ai-web-bridge"


def token_path() -> Path:
    return config_dir() / "extension_token"


def extension_host_config_path() -> Path:
    return config_dir() / "extension_host.json"


def create_pairing_token(path: Path | None = None, rotate: bool = False) -> str:
    """Create or read the secret shared by the CLI and registered native host."""
    target = path or token_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not rotate:
        token = target.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            return token
    token = secrets.token_urlsafe(32)
    target.write_text(token + "\n", encoding="utf-8")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return token


def read_pairing_token(path: Path | None = None) -> str:
    target = path or token_path()
    try:
        token = target.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("Extension setup is incomplete. Run --extension-setup after loading the extension.") from exc
    if len(token) < 32:
        raise RuntimeError("The extension's local pairing secret is invalid. Run --extension-setup --extension-rotate.")
    return token


def _native_manifest_path(browser: str) -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return config_dir() / "native_messaging_host.json"
    if sys.platform == "darwin":
        roots = {
            "chrome": home / "Library" / "Application Support" / "Google" / "Chrome",
            "edge": home / "Library" / "Application Support" / "Microsoft Edge",
        }
    else:
        roots = {
            "chrome": home / ".config" / "google-chrome",
            "edge": home / ".config" / "microsoft-edge",
        }
    return roots[browser] / "NativeMessagingHosts" / f"{HOST_NAME}.json"


def _build_native_host() -> Path:
    """Build a standalone executable because native host manifests cannot pass script args."""
    host_script = Path(__file__).resolve().with_name("native_messaging_host.py")
    build_root = config_dir() / "native_host_build"
    dist_dir = build_root / "dist"
    work_dir = build_root / "work"
    executable_name = HOST_NAME.replace(".", "_")
    executable = dist_dir / (executable_name + (".exe" if sys.platform == "win32" else ""))
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        executable_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(work_dir),
        "--paths",
        str(host_script.parent),
        str(host_script),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Extension setup needs PyInstaller. Install project dependencies with `pip install -r requirements.txt`.") from exc
    except subprocess.CalledProcessError as exc:
        output = (exc.stdout or "").strip()
        raise RuntimeError("Could not build the native messaging host executable." + (f"\n{output[-3000:]}" if output else "")) from exc
    if not executable.is_file():
        raise RuntimeError(f"PyInstaller completed without creating the native host at {executable}.")
    return executable.resolve()


def setup_native_host(
    extension_ids: list[str],
    port: int = DEFAULT_EXTENSION_PORT,
    rotate: bool = False,
) -> list[str]:
    """Register this extension's Python native host for installed Chromium browsers."""
    normalized = []
    for extension_id in extension_ids:
        candidate = extension_id.strip()
        if candidate.startswith("chrome-extension://"):
            candidate = candidate[len("chrome-extension://"):].rstrip("/")
        if len(candidate) != 32 or any(char not in "abcdefghijklmnop" for char in candidate):
            raise ValueError(f"Invalid extension ID '{extension_id}'. Copy the 32-character ID from the browser extensions page.")
        origin = f"chrome-extension://{candidate}/"
        if origin not in normalized:
            normalized.append(origin)
    if not normalized:
        raise ValueError("Provide at least one browser extension ID with --extension-id.")
    if not 1 <= port <= 65535:
        raise ValueError("--extension-port must be between 1 and 65535.")

    host_executable = _build_native_host()

    token = create_pairing_token(rotate=rotate)
    config_dir().mkdir(parents=True, exist_ok=True)
    config_data = {
        "version": 1,
        "token": token,
        "allowed_origins": normalized,
        "port": port,
    }
    config_path = extension_host_config_path()
    config_path.write_text(json.dumps(config_data, indent=2) + "\n", encoding="utf-8")
    try:
        config_path.chmod(0o600)
    except OSError:
        pass

    manifest = {
        "name": HOST_NAME,
        "description": "AI Web Bridge local browser connector",
        "path": str(host_executable),
        "type": "stdio",
        "allowed_origins": normalized,
    }
    registered = []
    for browser in ("chrome", "edge"):
        target = _native_manifest_path(browser)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        registered.append(str(target))
        if sys.platform == "win32":
            import winreg

            company = "Google\\Chrome" if browser == "chrome" else "Microsoft\\Edge"
            key_path = f"Software\\{company}\\NativeMessagingHosts\\{HOST_NAME}"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(target))
    return registered


def _read_json_line(stream) -> dict[str, Any] | None:
    line = stream.readline(MAX_MESSAGE_BYTES + 1)
    if not line or len(line) > MAX_MESSAGE_BYTES:
        return None
    try:
        data = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json_line(stream, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_MESSAGE_BYTES:
        raise ValueError("Extension message exceeds the local bridge size limit.")
    stream.sendall(data + b"\n")


class _BridgeTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class ExtensionBridge:
    """Serve one pending job to an authenticated native-messaging host."""

    def __init__(self, port: int, token: str, allowed_origins: list[str] | None = None):
        self.port = port
        self.token = token
        self.allowed_origins = allowed_origins or self._saved_origins()
        self._condition = threading.Condition()
        self._job: dict[str, Any] | None = None
        self._result: dict[str, Any] | None = None
        self._claimed = False
        owner = self

        class Handler(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                connection = self.request
                reader = connection.makefile("rb")
                connection.settimeout(15)
                auth = _read_json_line(reader)
                if not auth or not secrets.compare_digest(str(auth.get("token", "")), owner.token):
                    _write_json_line(connection, {"ok": False, "error": "Native host authentication failed."})
                    return
                origin = str(auth.get("origin", ""))
                if origin not in owner.allowed_origins:
                    _write_json_line(connection, {"ok": False, "error": "This extension is not registered with the local bridge."})
                    return
                request = _read_json_line(reader)
                if not request:
                    _write_json_line(connection, {"ok": False, "error": "Invalid native host request."})
                    return
                action = request.get("action")
                try:
                    request_port = int(request.get("port", DEFAULT_EXTENSION_PORT))
                except (TypeError, ValueError):
                    _write_json_line(connection, {"ok": False, "error": "Invalid bridge port."})
                    return
                if not 1 <= request_port <= 65535 or request_port != owner.port:
                    _write_json_line(connection, {"ok": False, "error": "The extension and CLI bridge ports do not match."})
                    return
                if action == "status":
                    with owner._condition:
                        job = owner._job or {}
                        _write_json_line(connection, {
                            "ok": True,
                            "status": {
                                "ready": owner._job is not None,
                                "claimed": owner._claimed,
                                "provider": job.get("provider"),
                                "url": job.get("url"),
                            },
                        })
                    return
                if action == "result":
                    result = request.get("result")
                    with owner._condition:
                        if not owner._job or not owner._claimed:
                            _write_json_line(connection, {"ok": False, "error": "No extension request is waiting for a result."})
                            return
                        if not isinstance(result, dict) or result.get("id") != owner._job["id"]:
                            _write_json_line(connection, {"ok": False, "error": "The extension result does not match the waiting request."})
                            return
                        owner._result = {
                            "text": str(result.get("text", ""))[:MAX_MESSAGE_BYTES],
                            "url": str(result.get("url", ""))[:4000],
                            "model": str(result.get("model", ""))[:300],
                            "error": str(result.get("error", ""))[:2000],
                            "models": [str(item)[:300] for item in result.get("models", [])[:100]]
                            if isinstance(result.get("models", []), list) else [],
                        }
                        owner._condition.notify_all()
                    _write_json_line(connection, {"ok": True})
                    return
                if action != "start":
                    _write_json_line(connection, {"ok": False, "error": "Unsupported native host action."})
                    return
                tab_url = str(request.get("tab_url", ""))
                with owner._condition:
                    if not owner._job:
                        _write_json_line(connection, {"ok": False, "error": "No CLI request is waiting."})
                        return
                    if owner._claimed:
                        _write_json_line(connection, {"ok": False, "error": "This request is already being handled."})
                        return
                    expected_host = (urlsplit(str(owner._job["url"])).hostname or "").lower()
                    tab_raw = tab_url.strip()
                    if tab_raw and not tab_raw.startswith(("http://", "https://")):
                        tab_raw = "https://" + tab_raw
                    actual_host = (urlsplit(tab_raw).hostname or "").lower()
                    aliases = {
                        "chatgpt.com": {"chat.openai.com", "openai.com"},
                        "chat.openai.com": {"chatgpt.com", "openai.com"},
                        "x.com": {"grok.com", "twitter.com"},
                        "grok.com": {"x.com", "twitter.com"},
                        "blackbox.ai": {"www.blackbox.ai"},
                        "www.blackbox.ai": {"blackbox.ai"},
                    }
                    if actual_host != expected_host and not actual_host.endswith("." + expected_host) and not expected_host.endswith("." + actual_host) and actual_host not in aliases.get(expected_host, set()):
                        _write_json_line(connection, {
                            "ok": False,
                            "error": f"Open {expected_host} in the active tab (got {actual_host or tab_url}). The waiting request was not claimed.",
                        })
                        return
                    owner._claimed = True
                    _write_json_line(connection, {"ok": True, "job": owner._job})
                    return

        self._server = _BridgeTCPServer(("127.0.0.1", port), Handler)
        self.port = int(self._server.server_address[1])
        self._thread = threading.Thread(target=self._server.serve_forever, name="ai-web-bridge-extension", daemon=True)

    @staticmethod
    def _saved_origins() -> list[str]:
        try:
            data = json.loads(extension_host_config_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        origins = data.get("allowed_origins", []) if isinstance(data, dict) else []
        return origins if isinstance(origins, list) else []

    def start(self) -> "ExtensionBridge":
        self._thread.start()
        return self

    def run_job(self, job: dict[str, Any], timeout: int) -> dict[str, Any]:
        with self._condition:
            self._job = {**job, "id": secrets.token_urlsafe(16)}
            self._result = None
            self._claimed = False
            self._condition.notify_all()
            deadline = time.monotonic() + timeout
            while self._result is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        "No result arrived from the extension. Open the selected AI tab, click the AI Web Bridge icon, "
                        "and choose 'Run waiting request' before the timeout."
                    )
                self._condition.wait(min(remaining, 1.0))
            result = self._result
            self._job = None
            self._result = None
            self._claimed = False
        if result.get("error"):
            raise RuntimeError(result["error"])
        if job.get("action") not in {"doctor", "list_models"} and not result.get("text", "").strip():
            raise RuntimeError("The extension completed the request but returned no response text.")
        return result

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=1)

    def __enter__(self) -> "ExtensionBridge":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
