#!/usr/bin/env python3
"""CLI entry point for the browser-based AI bridge.

The default provider is configured in providers.json. Provider-specific browser
interaction lives behind adapters in bridge/providers/.
"""

import argparse
import asyncio
import importlib
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright

from config import ConfigurationError, browser_settings, load_config
from browser_profiles import default_user_data_dir, list_browser_profiles, validate_profile_directory
from chrome_existing_session import ChromeDevToolsSession, ChromeMcpContext
from context_packet import ContextPacketError, DEFAULT_CONTEXT_LIMIT_CHARS, load_context_packet
from extension_bridge import DEFAULT_EXTENSION_PORT, ExtensionBridge, read_pairing_token, setup_native_host
from providers import BrowserUnavailableError, ProviderError
from sessions import SessionStore
from usage_metrics import record_usage_sample, summarize_usage


WORKSPACE_DIR = Path(__file__).resolve().parent
CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


@dataclass
class QueryResult:
    response_text: str
    selected_model: str | None


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def find_browser(browser_name: str, explicit_path: str | None = None) -> str | None:
    if explicit_path and Path(explicit_path).exists():
        return explicit_path
    if explicit_path:
        return None
    if browser_name == "edge":
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:
        candidates = CHROME_PATHS
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def _session_profile_scope(provider_config: dict, settings: dict) -> str | None:
    """Keep legacy Chrome-default chat links while isolating other browser profiles."""
    if settings.get("mode") == "existing":
        return "chrome:existing-session"
    browser_name = settings["name"]
    browser = provider_config["browser"]
    profile_key = "edge_default_profile" if browser_name == "edge" else "default_profile"
    default_profile = Path(
        os.path.expanduser(browser.get(profile_key, "~/ArgonChromeProfile"))
    ).resolve()
    profile = Path(settings["profile"]).expanduser().resolve()
    if browser_name == "chrome" and profile == default_profile and settings.get("profile_directory") in (None, "Default"):
        return None
    directory = settings.get("profile_directory")
    if directory in (None, "Default"):
        return f"{browser_name}:{profile}"
    return f"{browser_name}:{profile}:{directory}"


def ensure_browser(settings: dict, start_url: str) -> subprocess.Popen | None:
    """Start a dedicated Chromium browser profile with CDP bound to localhost."""
    if settings.get("mode", "managed") == "existing":
        return None
    port = settings["port"]
    profile_directory = settings.get("profile_directory")
    print(f"Selected browser profile: {settings['name'].title()} / {settings['profile']} / {profile_directory or 'Default'}")
    if is_port_open(port, settings["host"]):
        print(
            f"Found an existing CDP endpoint at {settings['host']}:{port}. "
            "The bridge cannot verify which profile started it. Confirm it matches the selection shown above."
        )
        return None

    if settings["host"] not in {"127.0.0.1", "localhost", "::1"}:
        raise BrowserUnavailableError(
            f"No browser is listening at {settings['host']}:{port}. "
            "The launcher only starts a local browser; start a remote CDP endpoint separately."
        )

    browser_path = find_browser(settings["name"], settings["executable"])
    if not browser_path:
        raise BrowserUnavailableError(
            f"{settings['name'].title()} was not found. Set BROWSER_EXE to its executable path."
        )

    if profile_directory:
        selected_profile = settings["profile"] / profile_directory
        if not selected_profile.is_dir():
            raise BrowserUnavailableError(
                f"Browser profile '{profile_directory}' was not found under {settings['profile']}. "
                "Run --list-browser-profiles and use a listed directory name."
            )
    settings["profile"].mkdir(parents=True, exist_ok=True)
    command = [
        browser_path,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={settings['profile']}",
        f"--remote-allow-origins=http://localhost:{port},http://127.0.0.1:{port}",
        "--no-first-run",
        "--no-default-browser-check",
        start_url,
    ]
    if profile_directory:
        command.insert(-1, f"--profile-directory={profile_directory}")
    print(f"Launching {settings['name'].title()} with remote debugging on localhost:{port}…")
    try:
        proc = subprocess.Popen(
            command,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
    except (TypeError, AttributeError):
        proc = subprocess.Popen(command)

    for _ in range(30):
        time.sleep(0.5)
        if is_port_open(port):
            print(f"{settings['name'].title()} is ready.")
            return proc

    raise BrowserUnavailableError(
        f"{settings['name'].title()} did not open CDP port {port}. Run launch_chrome.bat or launch_chrome.sh, "
        "sign in to the provider, and retry."
    )


@asynccontextmanager
async def connected_browser_context(settings: dict, start_url: str, browser_session=None):
    """Yield either a user-approved live Chrome session or the managed CDP context."""
    if settings.get("mode", "managed") == "existing":
        owns_session = browser_session is None
        session = browser_session or await ChromeDevToolsSession().start()
        try:
            yield await ChromeMcpContext(session, start_url).initialize_pages()
        finally:
            if owns_session:
                await session.close()
        return

    ensure_browser(settings, start_url)
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.connect_over_cdp(
                f"http://{settings['host']}:{settings['port']}"
            )
        except Exception as exc:
            raise BrowserUnavailableError(
                f"Cannot connect to the configured Chromium browser on {settings['host']}:{settings['port']}. "
                "Start the bridge browser, sign in, and retry."
            ) from exc
        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        try:
            await context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass
        yield context


def create_provider(provider_id: str, config: dict):
    """Resolve a configured provider ID to its adapter implementation."""
    module_name, class_name = config["adapter"].split(":", 1)
    try:
        adapter_type = getattr(importlib.import_module(module_name), class_name)
    except (ImportError, AttributeError) as exc:
        raise ConfigurationError(
            f"Provider '{provider_id}' adapter '{config['adapter']}' could not be loaded."
        ) from exc
    return adapter_type(config)


def _run_extension_job(provider_id: str, provider_config: dict, settings: dict, job: dict, timeout: int) -> dict:
    """Wait for the user-invoked extension to process one local CLI job."""
    try:
        token = read_pairing_token()
    except RuntimeError as exc:
        raise BrowserUnavailableError(str(exc)) from exc
    try:
        bridge = ExtensionBridge(settings.get("port", DEFAULT_EXTENSION_PORT), token)
        bridge.start()
    except OSError as exc:
        raise BrowserUnavailableError(
            f"Could not start the local extension bridge on 127.0.0.1:{settings.get('port', DEFAULT_EXTENSION_PORT)}. "
            "Another app may already be using that port; choose another with --extension-port."
        ) from exc
    print(f"Provider: {provider_config['name']} ({provider_id})")
    print(f"Browser: {settings['name'].title()} / installed AI Web Bridge extension")
    print(f"Local connector port: 127.0.0.1:{bridge.port}")
    print(
        "Waiting for the extension. Open the signed-in provider tab, click the extension icon, "
        "then choose 'Run waiting request'."
    )
    try:
        try:
            return bridge.run_job(job, timeout)
        except TimeoutError as exc:
            raise BrowserUnavailableError(str(exc)) from exc
        except RuntimeError as exc:
            raise ProviderError(str(exc)) from exc
    finally:
        bridge.close()


async def _execute_extension_query(
    prompt: str,
    provider_id: str,
    provider_config: dict,
    settings: dict,
    model: str | None,
    output_file: str | None,
    new_chat: bool,
    timeout: int,
    list_only: bool,
    record_run: bool,
    prompt_ref: str | None,
    context_ref: str | None,
    return_details: bool,
    read_latest: bool = False,
) -> str | list[str] | QueryResult:
    """Run a provider task through the installed extension and its local loopback broker."""
    job = {
        "action": "read_latest" if read_latest else ("list_models" if list_only else "query"),
        "provider": provider_id,
        "url": provider_config["url"],
        "name": provider_config["name"],
        "selectors": provider_config["selectors"],
        "prompt": prompt,
        "model": model,
        "new_chat": new_chat,
        "timeout": timeout,
    }
    result = _run_extension_job(
        provider_id,
        provider_config,
        settings,
        job,
        timeout=timeout + 120,
    )
    if list_only:
        models = result.get("models", [])
        print("\nAvailable models:\n" + ("\n".join(f"  - {name}" for name in models) if models else "  (No model choices were detected.)"))
        return models

    response_text = result["text"]
    selected_model = result.get("model") or model
    sessions = SessionStore(profile_scope=f"extension:{settings['name']}")
    if result.get("url"):
        sessions.save_chat_url(provider_id, result["url"])
    if record_run:
        sessions.append_run({
            "provider": provider_id,
            "provider_name": provider_config["name"],
            "model": selected_model,
            "chat_url": result.get("url"),
            "prompt_ref": prompt_ref,
            "context_ref": context_ref,
            "output_ref": str(Path(output_file).resolve()) if output_file else None,
        })
    if output_file:
        output_path = Path(output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response_text, encoding="utf-8")
        print(f"\nResponse saved → {output_path}")
    else:
        print("\n" + "=" * 42 + " RESPONSE " + "=" * 42)
        print(response_text)
        print("=" * 94 + "\n")
    if return_details:
        return QueryResult(response_text=response_text, selected_model=selected_model)
    return response_text


async def execute_query(
    prompt: str,
    provider_id: str,
    provider_config: dict,
    connection_settings: dict | None = None,
    model: str | None = None,
    output_file: str | None = None,
    new_chat: bool = False,
    timeout: int = 300,
    list_only: bool = False,
    record_run: bool = False,
    prompt_ref: str | None = None,
    context_ref: str | None = None,
    return_details: bool = False,
    diagnostics_dir: str | None = None,
    browser_session: ChromeDevToolsSession | None = None,
    read_latest: bool = False,
) -> str | list[str] | QueryResult:
    browser_settings_value = connection_settings or browser_settings(provider_config)
    if browser_settings_value.get("mode") == "extension":
        return await _execute_extension_query(
            prompt,
            provider_id,
            provider_config,
            browser_settings_value,
            model,
            output_file,
            new_chat,
            timeout,
            list_only,
            record_run,
            prompt_ref,
            context_ref,
            return_details,
            read_latest=read_latest,
        )

    provider = create_provider(provider_id, provider_config)
    port = browser_settings_value["port"]
    sessions = SessionStore(
        profile_scope=_session_profile_scope(provider_config, browser_settings_value)
    )

    async with connected_browser_context(browser_settings_value, provider.url, browser_session) as context:
        try:
            chat_url = None if new_chat else sessions.get_chat_url(provider_id)
            page = await provider.open_or_resume_chat(context, chat_url=chat_url, new_chat=new_chat)
            login_timeout = int(provider_config.get("timeouts", {}).get("login_seconds", 120))
            await provider.wait_for_login(page, timeout=login_timeout)

            if list_only:
                models = await provider.list_models(page)
                print("\nAvailable models:\n" + "\n".join(f"  - {name}" for name in models))
                if not models:
                    print("  (No model choices were detected in the provider UI.)")
                return models

            selected_model = await provider.select_model(page, model) if model else None

            initial_count = len(await provider.get_response_elements(page))
            try:
                await provider.send_prompt(page, prompt)
                response_text = await provider.wait_for_response(
                    page,
                    initial_count=initial_count,
                    timeout=timeout,
                )
            except Exception:
                try:
                    if diagnostics_dir:
                        diagnostic_path = Path(diagnostics_dir).expanduser().resolve()
                        diagnostic_path.mkdir(parents=True, exist_ok=True)
                        screenshot_name = diagnostic_path / f"debug_{provider_id}.png"
                        await page.screenshot(path=str(screenshot_name))
                        print(f"Saved requested diagnostic screenshot → {screenshot_name}")
                except Exception:
                    pass
                raise

            refresh_url = getattr(page, "refresh_url", None)
            if refresh_url:
                await refresh_url()
            sessions.save_chat_url(provider_id, page.url)
            if record_run:
                sessions.append_run({
                    "provider": provider_id,
                    "provider_name": provider.name,
                    "model": selected_model,
                    "chat_url": page.url,
                    "prompt_ref": prompt_ref,
                    "context_ref": context_ref,
                    "output_ref": str(Path(output_file).resolve()) if output_file else None,
                })
            if output_file:
                output_path = Path(output_file).resolve()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(response_text, encoding="utf-8")
                print(f"\nResponse saved → {output_path}")
            else:
                print("\n" + "=" * 42 + " RESPONSE " + "=" * 42)
                print(response_text)
                print("=" * 94 + "\n")

            if return_details:
                return QueryResult(response_text=response_text, selected_model=selected_model)
            return response_text
        finally:
            await provider.close()


def _multi_output_path(base: str | None, provider_id: str, label: str = "response") -> Path:
    if base:
        path = Path(base).expanduser()
        suffix = path.suffix or ".md"
        stem = path.stem if path.suffix else path.name
        return path.with_name(f"{stem}.{provider_id}.{label}{suffix}").resolve()
    return (Path.cwd() / f"_argon_{label}_{provider_id}.md").resolve()


def _build_comparison_prompt(original_prompt: str, results: list[dict], max_chars: int) -> str:
    prefix = (
        "Compare these independent browser-AI responses. Identify agreement, "
        "meaningful disagreement, and the most actionable conclusion. Do not "
        "repeat their full reasoning.\n\n"
    )
    if len(prefix) >= max_chars:
        raise ContextPacketError("The context limit is too small to build a comparison request.")
    task_header = "## Original task context\n"
    task_budget = min(len(original_prompt), max(0, (max_chars - len(prefix) - len(task_header)) // 3))
    task_excerpt = original_prompt[:task_budget]
    if task_budget < len(original_prompt):
        task_excerpt += "\n[Original context excerpt shortened to fit comparison limit]"
    result_sections = []
    for item in results:
        result_sections.append((f"## Response from {item['provider']}\n", item["response"]))

    fixed = prefix + task_header + task_excerpt + "\n\n"
    remaining = max_chars - len(fixed)
    rendered_sections = [fixed.rstrip()]
    for index, (header, response) in enumerate(result_sections):
        separator = "\n\n"
        available = remaining - len(separator) - len(header)
        responses_left = len(result_sections) - index
        fair_share = max(0, available // responses_left)
        marker = "\n[Response excerpt truncated to fit comparison limit]"
        if len(response) > fair_share:
            response = (
                response[:fair_share - len(marker)] + marker
                if fair_share >= len(marker)
                else response[:fair_share]
            )
        section = separator + header + response
        if len(section) > remaining:
            break
        rendered_sections.append(section)
        remaining -= len(section)
    return "".join(rendered_sections)[:max_chars]


def _load_provider_tasks(path: str | Path, configured_providers: dict) -> dict[str, str]:
    """Read a compact v1 provider-to-task assignment file."""
    tasks_path = Path(path).expanduser().resolve()
    try:
        packet = json.loads(tasks_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read a valid tasks JSON file: {exc}") from exc
    if not isinstance(packet, dict) or packet.get("version") != 1:
        raise ValueError("Tasks file must be a JSON object with version 1.")
    tasks = packet.get("tasks")
    if not isinstance(tasks, dict) or not tasks:
        raise ValueError("Tasks file requires a non-empty 'tasks' object mapping provider IDs to task strings.")
    if any(not isinstance(key, str) or not isinstance(value, str) or not value.strip()
           for key, value in tasks.items()):
        raise ValueError("Each task must map a provider ID to a non-empty string.")
    unknown = [provider for provider in tasks if provider not in configured_providers]
    if unknown:
        raise ValueError("Unknown provider(s) in tasks file: " + ", ".join(unknown))
    return tasks


def _connection_settings_for(provider_config: dict, args) -> dict:
    settings = browser_settings(provider_config)
    if args.browser:
        settings["name"] = args.browser
        profile_env = provider_config["browser"].get(
            "edge_profile_env" if args.browser == "edge" else "profile_env"
        )
        custom_root = args.profile_dir or os.environ.get("BROWSER_PROFILE_DIR") or (os.environ.get(profile_env) if profile_env else None)
        if custom_root:
            settings["profile"] = Path(custom_root).expanduser().resolve()
        else:
            if args.profile_directory or settings.get("profile_directory"):
                settings["profile"] = default_user_data_dir(args.browser).resolve()
            else:
                browser_config = provider_config["browser"]
                profile_key = "edge_default_profile" if args.browser == "edge" else "default_profile"
                settings["profile"] = Path(
                    os.path.expanduser(browser_config.get(profile_key, "~/ArgonChromeProfile"))
                ).resolve()
    if args.profile_directory:
        try:
            settings["profile_directory"] = validate_profile_directory(args.profile_directory)
        except ValueError as exc:
            raise ConfigurationError(str(exc)) from exc
        profile_override_present = any(
            os.environ.get(name)
            for name in (
                "BROWSER_PROFILE_DIR",
                provider_config["browser"].get(
                    "edge_profile_env" if settings["name"] == "edge" else "profile_env", ""
                ),
            )
            if name
        )
        if not args.profile_dir and not profile_override_present:
            settings["profile"] = default_user_data_dir(settings["name"]).resolve()
        if not args.cdp_port:
            try:
                settings["port"] = int(os.environ.get("CDP_PORT", "9222"))
            except ValueError as exc:
                raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.") from exc
            if not 1 <= settings["port"] <= 65535:
                raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.")
    if args.cdp_host:
        settings["host"] = args.cdp_host
    if args.cdp_port:
        settings["port"] = args.cdp_port
    if args.profile_dir:
        settings["profile"] = Path(args.profile_dir).expanduser().resolve()
        if not args.cdp_port:
            try:
                shared_port = int(os.environ.get("CDP_PORT", "9222"))
            except ValueError as exc:
                raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.") from exc
            if not 1 <= shared_port <= 65535:
                raise ConfigurationError("CDP_PORT must be an integer between 1 and 65535.")
            settings["port"] = shared_port
    if args.browser_mode:
        settings["mode"] = args.browser_mode
    if settings.get("mode") == "existing" and settings["name"] != "chrome":
        raise ConfigurationError("Existing-session mode currently supports Chrome only; select --browser chrome.")
    if settings.get("mode") == "extension":
        if not 1 <= args.extension_port <= 65535:
            raise ConfigurationError("--extension-port must be an integer between 1 and 65535.")
        settings["port"] = args.extension_port
    return settings


async def execute_multi_query(
    prompt: str,
    provider_ids: list[str],
    config: dict,
    args,
    prompt_ref: str | None,
    context_ref: str | None,
    provider_tasks: dict[str, str] | None = None,
) -> int:
    """Run providers sequentially so shared CDP profiles cannot collide."""
    results: list[dict] = []
    timeout = args.timeout or 300
    interrupted = False
    first_settings = _connection_settings_for(config["providers"][provider_ids[0]], args)
    browser_session = await ChromeDevToolsSession().start() if first_settings.get("mode") == "existing" else None
    for provider_id in provider_ids:
        provider_config = config["providers"][provider_id]
        output_path = _multi_output_path(args.output, provider_id)
        started = time.monotonic()
        provider_prompt = prompt
        if provider_tasks and provider_id in provider_tasks:
            provider_prompt += "\n\n## Assigned task for this AI\n" + provider_tasks[provider_id]
        try:
            query_result = await execute_query(
                provider_prompt,
                provider_id=provider_id,
                provider_config=provider_config,
                connection_settings=_connection_settings_for(provider_config, args),
                model=args.provider_models.get(provider_id, args.model),
                output_file=str(output_path),
                new_chat=args.new_chat,
                timeout=args.timeout or int(provider_config.get("timeouts", {}).get("response_seconds", timeout)),
                record_run=args.record_run,
                prompt_ref=prompt_ref,
                context_ref=context_ref,
                return_details=True,
                diagnostics_dir=args.diagnostics_dir,
                browser_session=browser_session,
            )
            if not isinstance(query_result, QueryResult):
                raise ProviderError(f"Provider '{provider_id}' did not return a response result.")
            results.append({
                "provider": provider_id,
                "status": "success",
                "model": query_result.selected_model,
                "duration": time.monotonic() - started,
                "output": str(output_path),
                "response": query_result.response_text,
            })
        except asyncio.CancelledError:
            interrupted = True
            results.append({
                "provider": provider_id,
                "status": "cancelled",
                "model": None,
                "duration": time.monotonic() - started,
                "output": str(output_path),
                "error": "Run interrupted; later providers were not started.",
                "response": "",
            })
            break
        except Exception as exc:
            results.append({
                "provider": provider_id,
                "status": "failed",
                "model": None,
                "duration": time.monotonic() - started,
                "output": str(output_path),
                "error": " ".join(str(exc).split())[:400] or type(exc).__name__,
                "response": "",
            })

    comparison_result = None
    if args.compare_provider:
        successful = [result for result in results if result["status"] == "success"]
        if len(successful) < 2:
            comparison_result = {
                "provider": f"comparison via {args.compare_provider}",
                "status": "skipped",
                "error": "At least two provider responses must succeed.",
            }
        else:
            compare_config = config["providers"][args.compare_provider]
            compare_path = _multi_output_path(args.output, args.compare_provider, "comparison")
            comparison_context = prompt
            if provider_tasks:
                assignments = "\n".join(
                    f"- {provider_id}: {task}" for provider_id, task in provider_tasks.items()
                )
                comparison_context += "\n\n## Provider assignments\n" + assignments
            comparison_prompt = _build_comparison_prompt(comparison_context, successful, args.context_limit_chars)
            started = time.monotonic()
            try:
                comparison_result_details = await execute_query(
                    comparison_prompt,
                    provider_id=args.compare_provider,
                    provider_config=compare_config,
                    connection_settings=_connection_settings_for(compare_config, args),
                    model=args.provider_models.get(args.compare_provider, args.model),
                    output_file=str(compare_path),
                    new_chat=True,
                    timeout=args.timeout or int(compare_config.get("timeouts", {}).get("response_seconds", timeout)),
                    record_run=args.record_run,
                    prompt_ref="<multi-provider comparison>",
                    context_ref=context_ref,
                    return_details=True,
                    diagnostics_dir=args.diagnostics_dir,
                    browser_session=browser_session,
                )
                if not isinstance(comparison_result_details, QueryResult):
                    raise ProviderError("Comparison provider did not return a response result.")
                comparison_result = {
                    "provider": f"comparison via {args.compare_provider}",
                    "status": "success",
                    "model": comparison_result_details.selected_model,
                    "duration": time.monotonic() - started,
                    "output": str(compare_path),
                }
            except asyncio.CancelledError:
                interrupted = True
                comparison_result = {
                    "provider": f"comparison via {args.compare_provider}",
                    "status": "cancelled",
                    "error": "Comparison interrupted.",
                    "duration": time.monotonic() - started,
                    "output": str(compare_path),
                }
            except Exception as exc:
                comparison_result = {
                    "provider": f"comparison via {args.compare_provider}",
                    "status": "failed",
                    "error": " ".join(str(exc).split())[:400] or type(exc).__name__,
                    "duration": time.monotonic() - started,
                    "output": str(compare_path),
                }

    if browser_session:
        await browser_session.close()

    print("\nMulti-provider run summary:")
    for result in results + ([comparison_result] if comparison_result else []):
        model_label = f"; model={result['model']}" if result.get("model") else ""
        duration = f"; {result['duration']:.1f}s" if result.get("duration") is not None else ""
        output = f"; output={result['output']}" if result.get("output") else ""
        error = f"; reason={result['error']}" if result.get("error") else ""
        print(f"- {result['provider']}: {result['status']}{model_label}{duration}{output}{error}")
    statuses = [result["status"] for result in results + ([comparison_result] if comparison_result else [])]
    return 130 if interrupted else (1 if any(status == "failed" for status in statuses) else 0)


async def run_doctor(provider_config: dict, provider_id: str, settings: dict) -> int:
    """Inspect configuration and current browser readiness without sending a prompt."""
    if settings.get("mode") == "extension":
        job = {
            "action": "doctor",
            "provider": provider_id,
            "url": provider_config["url"],
            "name": provider_config["name"],
            "selectors": provider_config["selectors"],
            "timeout": 10,
        }
        try:
            result = _run_extension_job(provider_id, provider_config, settings, job, timeout=120)
        except Exception as exc:
            print(f"Status: {exc}")
            return 1
        print(f"Status: {result['text']}")
        for model_name in result.get("models", []):
            print(f"  - {model_name}")
        return 0

    if settings.get("mode") == "existing":
        print(f"Provider: {provider_config['name']} ({provider_id})")
        print("Browser: Chrome / existing signed-in session")
        try:
            session = await ChromeDevToolsSession().start()
            try:
                context = await ChromeMcpContext(session, provider_config["url"]).initialize_pages()
                provider_host = provider_config["url"].split("/")[2]
                page = next((item for item in context.pages if provider_host in item.url), None)
                if not page:
                    print(f"Status: Chrome is connected, but {provider_config['name']} is not open.")
                    print(f"Next: open {provider_config['url']} in your Chrome profile and rerun --doctor.")
                    return 1
                try:
                    input_element = await page.wait_for_selector(
                        provider_config["selectors"]["input"], timeout=5000, state="visible"
                    )
                except Exception:
                    input_element = None
                if not input_element:
                    print("Status: Chrome is connected, but the provider chat input is not ready or sign-in is required.")
                    return 1
                print("Status: signed in and ready; provider chat input is visible. No prompt was sent.")
                provider = create_provider(provider_id, provider_config)
                try:
                    models = await provider.list_models(page)
                finally:
                    await provider.close()
                if models:
                    print("Models currently visible to this account:")
                    for model_name in models:
                        print(f"  - {model_name}")
                else:
                    print("Model choices were not detected; the site may not expose a picker on this page.")
                return 0
            finally:
                await session.close()
        except Exception as exc:
            print(f"Status: Could not connect to the existing Chrome session: {exc}")
            print("Next: use Chrome 144+, enable Remote Debugging at chrome://inspect/#remote-debugging, and approve the bridge.")
            return 1

    host, port = settings["host"], settings["port"]
    print(f"Provider: {provider_config['name']} ({provider_id})")
    print(f"Browser: {settings['name'].title()} / Chromium CDP")
    print(f"CDP endpoint: {host}:{port}")
    print(f"Browser data folder: {settings['profile']}")
    if settings.get("profile_directory"):
        print(f"Selected profile: {settings['profile_directory']}")

    if not is_port_open(port, host):
        print("Status: browser endpoint is not reachable.")
        print("Next: start the configured browser with bridge/launch_chrome.bat or bridge/launch_chrome.sh.")
        return 1

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.connect_over_cdp(f"http://{host}:{port}", timeout=5000)
            contexts = browser.contexts
            pages = [page for context in contexts for page in context.pages]
            provider_pages = [page for page in pages if provider_config["url"].split("/")[2] in page.url]
            if not provider_pages:
                if any("accounts.google.com" in page.url for page in pages):
                    print("Status: Google sign-in is required in the bridge browser.")
                    print("Next: finish signing in, open Gemini, then run --doctor again.")
                    return 1
                print(f"Status: browser is reachable, but {provider_config['name']} is not open.")
                print(f"Next: open {provider_config['url']} in the bridge browser and sign in.")
                return 1

            page = provider_pages[0]
            try:
                input_elem = await page.wait_for_selector(
                    provider_config["selectors"]["input"], timeout=2500, state="visible"
                )
            except Exception:
                input_elem = None
            if input_elem:
                print("Status: signed in and ready; provider chat input is visible. No prompt was sent.")
                provider = create_provider(provider_id, provider_config)
                try:
                    models = await provider.list_models(page)
                finally:
                    await provider.close()
                if models:
                    print("Models currently visible to this account:")
                    for model_name in models:
                        print(f"  - {model_name}")
                else:
                    print("Model choices were not detected; the site may not expose a picker on this page.")
                return 0
            if "accounts.google.com" in page.url or "/login" in page.url.casefold() or "/auth/" in page.url.casefold():
                print("Status: provider requires sign-in.")
                print("Next: finish signing in within the bridge browser, then run --doctor again.")
            else:
                print("Status: not ready; sign-in may be required or the provider chat page did not finish loading.")
                print("Next: confirm sign-in and page readiness. If the chat input remains missing, the provider UI selectors may need updating.")
            return 1
    except Exception as exc:
        print(f"Status: CDP endpoint responded, but Playwright could not inspect it: {exc}")
        print("Next: restart the bridge browser and check the configured host and port.")
        return 1


def main() -> None:
    try:
        config = load_config()
    except ConfigurationError as exc:
        sys.exit(f"Configuration error: {exc}")

    default_provider = config["default_provider"]
    parser = argparse.ArgumentParser(description="AI Web Bridge: send a prompt to a configured browser AI")
    parser.add_argument("--prompt", "-p", help="Prompt text to send")
    parser.add_argument("--provider", choices=tuple(config["providers"]), default=None,
                        help=f"Browser AI provider for a single-provider run (default: {default_provider})")
    fanout = parser.add_mutually_exclusive_group()
    fanout.add_argument("--providers", help="Comma-separated provider IDs for an explicit multi-provider run")
    fanout.add_argument("--all", action="store_true", help="Send the request to every configured provider")
    fanout.add_argument("--tasks-file", help="JSON file assigning a distinct task to each provider")
    parser.add_argument("--compare-provider", choices=tuple(config["providers"]),
                        help="Optionally ask this provider to synthesize successful multi-provider replies")
    parser.add_argument("--provider-model", action="append", default=[], metavar="ID=LABEL",
                        help="Override --model for one provider; repeat for multiple provider-specific model labels")
    parser.add_argument("--list-providers", action="store_true", help="List configured provider adapters")
    parser.add_argument("--prompt-file", "--file", "-f", dest="file", help="File containing the prompt")
    parser.add_argument("--context-file", help="Version 1 JSON project context packet")
    parser.add_argument("--context-limit-chars", type=int, default=DEFAULT_CONTEXT_LIMIT_CHARS,
                        help=f"Maximum assembled context size (default: {DEFAULT_CONTEXT_LIMIT_CHARS})")
    parser.add_argument("--review-context", action="store_true",
                        help="Print the exact assembled prompt and exit without opening a browser")
    parser.add_argument("--record-run", action="store_true",
                        help="Opt in to local metadata-only run logging under .ai-web-bridge/runs.jsonl")
    parser.add_argument("--no-handoff", action="store_true",
                        help="Do not load or save the compact project handoff for this request")
    parser.add_argument("--forget-local-data", action="store_true",
                        help="Remove saved chat links, run records, usage samples, and handoff for this project")
    parser.add_argument("--forget-chats", action="store_true", help="Remove this project's saved browser chat links")
    parser.add_argument("--forget-runs", action="store_true", help="Remove this project's optional run records")
    parser.add_argument("--forget-handoff", action="store_true", help="Remove this project's compact saved handoff")
    parser.add_argument("--forget-usage", action="store_true", help="Remove this project's token comparison samples")
    parser.add_argument("--yes", action="store_true", help="Confirm a local-data removal action")
    parser.add_argument("--record-usage-sample", action="store_true",
                        help="Record token counts reported by a CLI; does not send a browser-AI request")
    parser.add_argument("--usage-report", action="store_true", help="Summarize locally recorded token comparisons")
    parser.add_argument("--usage-file", default=None, help="Usage sample file (default: project-local metadata folder)")
    parser.add_argument("--usage-task", help="Short category label for a comparable task, not the prompt text")
    for metric in ("baseline-input-tokens", "baseline-output-tokens", "bridge-input-tokens", "bridge-output-tokens"):
        parser.add_argument(f"--{metric}", type=int, help=f"Token count reported by your coding CLI ({metric})")
    parser.add_argument("--diagnostics-dir", help="Opt in to saving page screenshots on query errors (may contain private chat data)")
    parser.add_argument("--model", "-m", default=None, help="Visible model label to select in the provider UI")
    parser.add_argument("--output", "--out", "-o", dest="output", help="File to save the response into")
    parser.add_argument("--new-chat", "-n", action="store_true", help="Start a fresh provider conversation")
    parser.add_argument("--timeout", "-t", type=int, help="Maximum seconds to wait (default: provider configuration, currently 300)")
    parser.add_argument("--list-models", action="store_true", help="List model choices visible in the provider UI")
    parser.add_argument("--launch-only", action="store_true", help="Open the configured browser and exit")
    parser.add_argument("--doctor", action="store_true", help="Check browser/provider setup without sending a prompt")
    parser.add_argument("--read-latest", action="store_true",
                        help="Read the latest assistant response from the open provider tab without submitting a new prompt")
    parser.add_argument("--list-browser-profiles", action="store_true",
                        help="List named profiles available in the selected browser")
    parser.add_argument("--browser", choices=("chrome", "edge"), help="Browser to use (default: BROWSER or chrome)")
    parser.add_argument("--browser-mode", choices=("managed", "existing", "extension"),
                        help="Use a managed profile, approved Chrome session, or browser extension")
    parser.add_argument("--extension-setup", action="store_true",
                        help="Register the local native host for the browser extension")
    parser.add_argument("--extension-rotate", action="store_true",
                        help="Rotate the local extension secret (requires --extension-setup)")
    parser.add_argument("--extension-id", action="append", default=[],
                        help="Browser extension ID to authorize; repeat to register Chrome and Edge IDs")
    parser.add_argument("--extension-port", type=int, default=DEFAULT_EXTENSION_PORT,
                        help=f"Local extension bridge port (default: {DEFAULT_EXTENSION_PORT})")
    parser.add_argument("--cdp-host", help="CDP host (defaults to localhost)")
    parser.add_argument("--cdp-port", type=int, help="CDP port (default: CDP_PORT, CHROME_DEBUG_PORT, or 9222)")
    parser.add_argument("--profile-dir", help="Dedicated browser profile directory")
    parser.add_argument("--profile-directory", help="Named browser profile folder, such as Default or Profile 1")
    args = parser.parse_args()

    if args.extension_rotate and not args.extension_setup:
        parser.error("--extension-rotate requires --extension-setup.")
    if args.extension_id and not args.extension_setup:
        parser.error("--extension-id requires --extension-setup.")
    if args.extension_setup:
        if not 1 <= args.extension_port <= 65535:
            parser.error("--extension-port must be between 1 and 65535.")
        try:
            registered = setup_native_host(args.extension_id, port=args.extension_port, rotate=args.extension_rotate)
        except (OSError, ValueError) as exc:
            parser.error(f"Could not register the browser extension: {exc}")
        print(f"Extension folder: {WORKSPACE_DIR.parent / 'browser-extension'}")
        print(f"Local bridge port: 127.0.0.1:{args.extension_port}")
        print("Native host registered for: " + ", ".join(args.extension_id))
        print("Registration files: " + ", ".join(registered))
        print("The native host only accepts the registered extension IDs. No pairing code needs to be copied.")
        return

    local_store = SessionStore()
    usage_path = Path(args.usage_file).expanduser().resolve() if args.usage_file else local_store.project_dir / ".ai-web-bridge" / "usage.jsonl"
    usage_counts = {
        "baseline_input_tokens": args.baseline_input_tokens,
        "baseline_output_tokens": args.baseline_output_tokens,
        "bridge_input_tokens": args.bridge_input_tokens,
        "bridge_output_tokens": args.bridge_output_tokens,
    }
    supplied_metrics = any(value is not None for value in usage_counts.values())
    if args.record_usage_sample:
        if not args.usage_task or any(value is None for value in usage_counts.values()):
            parser.error("--record-usage-sample requires --usage-task and all four token-count options.")
        try:
            sample = record_usage_sample(usage_path, args.usage_task, usage_counts)
        except ValueError as exc:
            parser.error(str(exc))
        print(
            f"Recorded {sample['task_label']}: baseline {sample['baseline_total_tokens']:,}, "
            f"bridge workflow {sample['bridge_total_tokens']:,}, change {sample['tokens_saved']:+,} tokens "
            f"({sample['reduction_percent']:+.2f}%)."
        )
        print("These are user-supplied CLI metrics, not a guaranteed savings estimate.")
        return
    if supplied_metrics or args.usage_task:
        parser.error("Token counts and --usage-task require --record-usage-sample.")
    if args.usage_report:
        try:
            summaries = summarize_usage(usage_path)
        except FileNotFoundError:
            parser.error(f"No usage samples found at {usage_path}.")
        except ValueError as exc:
            parser.error(str(exc))
        if not summaries:
            print("No usage samples have been recorded.")
        for item in summaries:
            print(
                f"{item['task_label']} ({item['samples']} sample(s)): "
                f"baseline {item['baseline_total_tokens']:,}, bridge workflow {item['bridge_total_tokens']:,}, "
                f"change {item['tokens_saved']:+,} ({item['reduction_percent']:+.2f}%)."
            )
        print("Results compare only the CLI token counts you recorded; they are task-specific.")
        return

    forget_categories = set()
    if args.forget_local_data:
        forget_categories = {"chats", "runs", "handoff", "usage"}
    else:
        if args.forget_chats:
            forget_categories.add("chats")
        if args.forget_runs:
            forget_categories.add("runs")
        if args.forget_handoff:
            forget_categories.add("handoff")
        if args.forget_usage:
            forget_categories.add("usage")
    if forget_categories:
        labels = ", ".join(sorted(forget_categories))
        if not args.yes:
            if not sys.stdin.isatty():
                parser.error(f"Removing local {labels} requires --yes when input is not interactive.")
            if input(f"Remove this project's saved {labels}? [y/N] ").strip().casefold() not in {"y", "yes"}:
                print("No local data was removed.")
                return
        removed = local_store.clear_local_data(forget_categories)
        print("Removed " + (", ".join(str(path) for path in removed) if removed else "no matching saved files"))
        return

    try:
        if args.list_providers:
            if args.providers or args.all or args.tasks_file or args.compare_provider:
                parser.error("--list-providers cannot be combined with multi-provider options.")
            for provider_name, provider_details in config["providers"].items():
                create_provider(provider_name, provider_details)
                default_label = " (default)" if provider_name == default_provider else ""
                print(f"{provider_name}\t{provider_details['name']}{default_label}")
            return

        multi_mode = bool(args.providers or args.all or args.tasks_file)
        if multi_mode and args.provider:
            parser.error("Use --providers or --all instead of --provider for a multi-provider run.")
        if args.compare_provider and not multi_mode:
            parser.error("--compare-provider requires --providers or --all.")
        if multi_mode and (args.list_models or args.launch_only or args.doctor or args.list_browser_profiles):
            parser.error("Multi-provider mode cannot be combined with --list-models, --launch-only, --doctor, or --list-browser-profiles.")
        provider_tasks = None
        if args.tasks_file:
            try:
                provider_tasks = _load_provider_tasks(args.tasks_file, config["providers"])
            except ValueError as exc:
                parser.error(str(exc))
            provider_ids = list(provider_tasks)
        elif args.providers:
            provider_ids = [provider.strip() for provider in args.providers.split(",")]
            if any(not provider for provider in provider_ids):
                parser.error("--providers contains an empty provider ID.")
            if len(provider_ids) != len(set(provider_ids)):
                parser.error("--providers cannot contain duplicate provider IDs.")
            unknown = [provider for provider in provider_ids if provider not in config["providers"]]
            if unknown:
                parser.error("Unknown provider(s): " + ", ".join(unknown))
        elif args.all:
            provider_ids = list(config["providers"])
        else:
            provider_ids = [args.provider or default_provider]
        args.provider_models = {}
        for model_spec in args.provider_model:
            provider_name, separator, model_label = model_spec.partition("=")
            if not separator or not provider_name or not model_label.strip():
                parser.error("--provider-model must use PROVIDER=VISIBLE_MODEL_LABEL.")
            if provider_name not in config["providers"]:
                parser.error(f"Unknown provider in --provider-model: {provider_name}")
            if provider_name in args.provider_models:
                parser.error(f"--provider-model was repeated for {provider_name}.")
            if provider_name not in provider_ids and provider_name != args.compare_provider:
                parser.error(f"--provider-model names {provider_name}, which is not selected for this run.")
            args.provider_models[provider_name] = model_label.strip()
        selected_provider = provider_ids[0]
        provider_config = config["providers"][selected_provider]
        browser_settings_value = _connection_settings_for(provider_config, args)
        if args.list_browser_profiles:
            configured_root = (
                args.profile_dir
                or os.environ.get("BROWSER_PROFILE_DIR")
                or os.environ.get(provider_config["browser"].get(
                    "edge_profile_env" if browser_settings_value["name"] == "edge" else "profile_env", ""
                ))
            )
            profile_root = Path(configured_root).expanduser().resolve() if configured_root else default_user_data_dir(browser_settings_value["name"])
            profiles = list_browser_profiles(profile_root)
            print(f"Browser: {browser_settings_value['name'].title()}\nProfile folder: {profile_root}")
            if profiles:
                print("Available profiles (use the directory value with --profile-directory):")
                for item in profiles:
                    print(f"  {item['directory']}\t{item['name']}")
            else:
                print("No named profiles were found. Check the selected browser's user-data folder or use --profile-dir.")
            return
        if args.launch_only:
            if browser_settings_value.get("mode") == "existing":
                async def connect_existing_chrome():
                    session = await ChromeDevToolsSession().start()
                    await session.close()
                asyncio.run(connect_existing_chrome())
            elif browser_settings_value.get("mode") == "extension":
                print(
                    f"Open {provider_config['url']} in the browser with the AI Web Bridge extension, "
                    "then use --browser-mode extension for a request."
                )
            else:
                ensure_browser(browser_settings_value, provider_config["url"])
            return

        if args.doctor:
            exit_code = asyncio.run(
                run_doctor(provider_config, selected_provider, browser_settings_value)
            )
            if exit_code:
                raise SystemExit(exit_code)
            return

        if args.read_latest:
            asyncio.run(
                execute_query(
                    "",
                    provider_id=selected_provider,
                    provider_config=provider_config,
                    connection_settings=browser_settings_value,
                    output_file=args.output,
                    read_latest=True,
                )
            )
            return

        if args.list_models:
            asyncio.run(
                execute_query(
                    "",
                    provider_id=selected_provider,
                    provider_config=provider_config,
                    connection_settings=browser_settings_value,
                    list_only=True,
                )
            )
            return

        prompt_ref = None
        if args.file:
            prompt_path = Path(args.file)
            if not prompt_path.exists():
                sys.exit(f"Error: prompt file '{args.file}' not found.")
            prompt = prompt_path.read_text(encoding="utf-8")
            prompt_ref = str(prompt_path.resolve())
        elif args.prompt:
            prompt = args.prompt
            prompt_ref = "<inline>"
        else:
            default_file = Path.cwd() / "prompt.txt"
            if default_file.exists() and not args.context_file:
                prompt = default_file.read_text(encoding="utf-8")
                prompt_ref = str(default_file.resolve())
            elif args.context_file or args.tasks_file:
                prompt = ""
            else:
                sys.exit("Error: no prompt supplied. Use --prompt TEXT or --prompt-file FILE.")

        context_ref = None
        if args.context_file:
            context_path = Path(args.context_file).expanduser().resolve()
            context_ref = str(context_path)
            extra = f"\n\n## Additional request\n{prompt.strip()}" if prompt.strip() else ""
            packet_budget = args.context_limit_chars - len(extra)
            if packet_budget < 1:
                raise ContextPacketError("The additional request alone exceeds the configured context limit.")
            saved_handoff = {} if args.no_handoff else local_store.load_handoff()
            context, notes = load_context_packet(context_path, packet_budget, handoff=saved_handoff)
            for note in notes:
                print(f"Context note: {note}", file=sys.stderr)
            prompt = context + extra
            if len(prompt) > args.context_limit_chars:
                raise ContextPacketError(
                    f"Assembled context is {len(prompt):,} characters; the limit is {args.context_limit_chars:,}. "
                    "Shorten the additional request or context packet."
                )
        elif args.context_limit_chars != DEFAULT_CONTEXT_LIMIT_CHARS:
            print("Note: --context-limit-chars applies only when --context-file is used.", file=sys.stderr)

        if not prompt.strip() and not provider_tasks:
            sys.exit("Error: the assembled prompt is empty.")
        if multi_mode:
            print(
                ("Task-routing mode assigns a distinct task to: " if provider_tasks else
                 "Multi-provider mode will send the same assembled prompt/context to: ")
                + ", ".join(provider_ids)
                + ". Providers run sequentially and receive separate output files.",
                file=sys.stderr,
            )
            if args.compare_provider:
                print(
                    f"Comparison is enabled: {args.compare_provider} will also receive successful response excerpts.",
                    file=sys.stderr,
                )
        if args.review_context:
            if provider_tasks:
                for provider_id, assigned_task in provider_tasks.items():
                    provider_prompt = prompt + "\n\n## Assigned task for this AI\n" + assigned_task
                    print(f"--- Request for {provider_id} ({len(provider_prompt):,} characters) ---")
                    print(provider_prompt)
                    print()
            else:
                print(prompt)
            return

        if args.context_file and not args.no_handoff:
            packet_data = json.loads(Path(args.context_file).expanduser().resolve().read_text(encoding="utf-8"))
            local_store.save_handoff(packet_data)

        if multi_mode:
            exit_code = asyncio.run(
                execute_multi_query(
                    prompt,
                    provider_ids=provider_ids,
                    config=config,
                    args=args,
                    prompt_ref=prompt_ref,
                    context_ref=context_ref,
                    provider_tasks=provider_tasks,
                )
            )
            if exit_code:
                raise SystemExit(exit_code)
        else:
            asyncio.run(
                execute_query(
                    prompt,
                    provider_id=selected_provider,
                    provider_config=provider_config,
                    connection_settings=browser_settings_value,
                    model=args.provider_models.get(selected_provider, args.model),
                    output_file=args.output,
                    new_chat=args.new_chat,
                    timeout=args.timeout or int(provider_config.get("timeouts", {}).get("response_seconds", 300)),
                    record_run=args.record_run,
                    prompt_ref=prompt_ref,
                    context_ref=context_ref,
                    diagnostics_dir=args.diagnostics_dir,
                )
            )
    except ProviderError as exc:
        sys.exit(f"Bridge error: {exc}")
    except ConfigurationError as exc:
        sys.exit(f"Configuration error: {exc}")
    except ContextPacketError as exc:
        sys.exit(f"Context packet error: {exc}")
    except KeyboardInterrupt:
        print("Interrupted. Completed provider output files are preserved.", file=sys.stderr)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
