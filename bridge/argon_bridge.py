#!/usr/bin/env python3
"""
Argon-Gemini Web Automation Bridge
───────────────────────────────────────────────────────────────────────────────
Connects to Google Chrome via remote debugging (CDP, port 9222) to send prompts
to gemini.google.com and retrieve responses with full multi-turn support.

Works with Antigravity, Cursor, Aider, Claude Code, or any CLI that can call
a subprocess and read a file.

Environment variables (optional, override defaults):
  CHROME_PROFILE_DIR   Path to a dedicated Chrome profile  (default: ~/ArgonChromeProfile)
  CHROME_DEBUG_PORT    CDP port                             (default: 9222)
───────────────────────────────────────────────────────────────────────────────
"""

import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from playwright.async_api import async_playwright

# ── Configuration (all overridable via env vars) ──────────────────────────────

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]

WORKSPACE_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_DIR = Path(
    os.environ.get("CHROME_PROFILE_DIR", str(Path.home() / "ArgonChromeProfile"))
).resolve()
DEBUG_PORT = int(os.environ.get("CHROME_DEBUG_PORT", "9222"))

# ── CSS selectors (tune here when Google updates their UI) ────────────────────
SELECTORS = {
    "input": (
        "rich-textarea div[contenteditable='true'], "
        "div[contenteditable='true'][role='textbox'], "
        "div.ql-editor[contenteditable='true'], "
        "div[contenteditable='true'], "
        "textarea"
    ),
    "send_btn": (
        "button[aria-label*='Send message' i], "
        "button[aria-label*='Send' i], "
        "button.send-button, "
        "button[mattooltip*='Send' i], "
        "button[aria-label*='Submit' i]"
    ),
    "stop_btn": (
        "button[aria-label*='Stop' i], "
        "button[aria-label*='stop generating' i], "
        "button[aria-label*='stop response' i]"
    ),
    "response_container": "model-response, .model-response, [data-test-id='model-response']",
    "response_content": "message-content, .model-response-text, .markdown",
    "copy_btn": (
        "button[aria-label*='Copy' i], "
        "button[data-test-id='copy-button'], "
        "button[mattooltip*='Copy' i]"
    ),
    "model_btn": (
        "button[aria-label*='model' i], "
        "button[aria-label*='mode' i], "
        "[data-test-id='bard-mode-menu-button'], "
        "div.model-picker-container button, "
        "button[aria-haspopup='menu']"
    ),
    "menu_item": "[role='menuitem'], [role='option'], .mat-mdc-menu-item, button[mat-menu-item]",
    "new_chat": (
        "a[href='/app'][aria-label*='New chat' i], "
        "button[aria-label*='New chat' i], "
        "a[data-test-id='new-chat-button'], "
        "div[aria-label*='New chat' i]"
    ),
}


# ── Chrome helpers ────────────────────────────────────────────────────────────

def is_port_open(host: str = "127.0.0.1", port: int = DEBUG_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def find_chrome() -> str | None:
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None


def ensure_chrome() -> subprocess.Popen | None:
    """Start Chrome with remote debugging if not already running."""
    if is_port_open():
        return None

    chrome_path = find_chrome()
    if not chrome_path:
        raise RuntimeError(
            "Google Chrome not found. Install Chrome or set its path in CHROME_PATHS."
        )

    DEFAULT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        chrome_path,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={DEFAULT_PROFILE_DIR}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "https://gemini.google.com/app",
    ]
    print(f"Launching Chrome with remote debugging on port {DEBUG_PORT}…")
    try:
        proc = subprocess.Popen(
            cmd,
            creationflags=(
                subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            ),
            close_fds=True,
        )
    except (TypeError, AttributeError):
        proc = subprocess.Popen(cmd)

    for _ in range(30):
        time.sleep(0.5)
        if is_port_open():
            print("Chrome is ready.")
            return proc

    raise TimeoutError(
        f"Chrome did not open port {DEBUG_PORT} in time.\n"
        "Run launch_chrome.bat (Windows) or launch_chrome.sh (Mac/Linux) first,\n"
        "then log in to gemini.google.com, and retry."
    )


# ── Playwright helpers ────────────────────────────────────────────────────────

async def get_or_create_gemini_page(context, new_chat: bool = False):
    page = next((p for p in context.pages if "gemini.google.com" in p.url), None)
    if not page:
        page = await context.new_page()
        await page.goto("https://gemini.google.com/app")
    else:
        await page.bring_to_front()
        if new_chat:
            await start_new_chat(page)
    return page


async def wait_for_login(page, timeout: int = 120) -> None:
    print("Checking Gemini authentication status…")
    deadline = time.time() + timeout
    while time.time() < deadline:
        elem = await page.query_selector(SELECTORS["input"])
        if elem and await elem.is_visible():
            return
        if "accounts.google.com" in page.url:
            print("⚠  Not signed in. Please log into Google in the opened Chrome window.")
        await asyncio.sleep(2)
    raise TimeoutError(
        "Timed out waiting for the Gemini chat interface.\n"
        "Make sure you are signed into Google inside the debug-Chrome window."
    )


async def start_new_chat(page) -> None:
    try:
        btn = await page.query_selector(SELECTORS["new_chat"])
        if btn and await btn.is_visible():
            print("Starting a new chat session…")
            await btn.click()
            await asyncio.sleep(1.5)
    except Exception as e:
        print(f"(new chat note: {e})")


async def list_models(page) -> list[str]:
    try:
        btn = await page.query_selector(SELECTORS["model_btn"])
        if not btn:
            return []
        await btn.click()
        await asyncio.sleep(1)
        items = await page.query_selector_all(SELECTORS["menu_item"])
        models = [(await i.inner_text() or "").strip().replace("\n", " ") for i in items]
        await page.keyboard.press("Escape")
        return [m for m in models if m]
    except Exception:
        return []


async def select_model(page, model_name: str) -> None:
    print(f"Selecting model '{model_name}'…")
    try:
        btn = await page.query_selector(SELECTORS["model_btn"])
        if btn and await btn.is_visible():
            current = (await btn.inner_text() or "").strip()
            if model_name.lower() in current.lower():
                print(f"  Already active: {current}")
                return
            await btn.click()
            await asyncio.sleep(1)
            for opt in await page.query_selector_all(SELECTORS["menu_item"]):
                text = (await opt.inner_text() or "").strip()
                if model_name.lower() in text.lower():
                    print(f"  Selecting: {text}")
                    await opt.click()
                    await asyncio.sleep(1)
                    return
            await page.keyboard.press("Escape")
            print(f"  '{model_name}' not found in menu; keeping current model.")
    except Exception as e:
        print(f"(model selection note: {e})")


async def get_response_elements(page):
    for sel in [SELECTORS["response_container"], SELECTORS["response_content"]]:
        elems = await page.query_selector_all(sel)
        if elems:
            return elems
    return []


async def send_prompt(page, prompt_text: str) -> None:
    print("Locating prompt input…")
    input_elem = None
    try:
        input_elem = await page.wait_for_selector(SELECTORS["input"], timeout=10_000)
    except Exception:
        pass
    if not input_elem:
        raise RuntimeError(
            "Cannot find the Gemini chat input box.\n"
            "Make sure the page is fully loaded and you are signed in."
        )

    await input_elem.scroll_into_view_if_needed()
    await input_elem.click()
    await asyncio.sleep(0.3)
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await asyncio.sleep(0.1)

    print(f"Inserting prompt ({len(prompt_text)} characters)…")
    try:
        await page.keyboard.insert_text(prompt_text)
    except Exception:
        await page.evaluate(
            "([el, t]) => { el.focus(); el.innerText = t; "
            "el.dispatchEvent(new Event('input',{bubbles:true})); }",
            [input_elem, prompt_text],
        )

    await asyncio.sleep(0.5)
    await page.evaluate(
        "([el]) => { el.dispatchEvent(new Event('input',{bubbles:true})); "
        "el.dispatchEvent(new Event('change',{bubbles:true})); }",
        [input_elem],
    )
    await asyncio.sleep(0.3)

    # Click Send
    for sel in SELECTORS["send_btn"].split(", "):
        btn = await page.query_selector(sel.strip())
        if btn and await btn.is_visible() and await btn.is_enabled():
            await btn.click()
            print("Clicked Send button.")
            return
    print("Send button not found; pressing Enter…")
    await input_elem.press("Enter")


async def wait_for_response(page, initial_count: int = 0, timeout: int = 300) -> str:
    """
    Strictly waits for a NEW response (count > initial_count) to finish
    streaming before returning the text.  Never returns a stale old answer.
    """
    print(f"Waiting for new response (baseline: {initial_count} message(s))…")
    deadline = time.time() + timeout
    started = False

    # Wait for generation to start
    while time.time() < deadline:
        stop = await page.query_selector(SELECTORS["stop_btn"])
        if stop and await stop.is_visible():
            started = True
            break
        if len(await get_response_elements(page)) > initial_count:
            started = True
            break
        await asyncio.sleep(0.5)

    if not started:
        print("(Warning: stream start not detected — falling back to stability check)")

    print("Gemini is generating…")
    last_text, stable_since = "", time.time()

    while time.time() < deadline:
        stop = await page.query_selector(SELECTORS["stop_btn"])
        generating = stop is not None and await stop.is_visible()

        elems = await get_response_elements(page)
        if len(elems) > initial_count:
            try:
                curr = (await elems[-1].inner_text() or "").strip()
            except Exception:
                curr = ""
            if curr != last_text:
                last_text, stable_since = curr, time.time()
            elif not generating and len(curr) > 0 and (time.time() - stable_since) >= 2.5:
                print("Generation complete.")
                break
        await asyncio.sleep(0.8)

    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(1.0)

    # Strategy 1: Copy button → clean Markdown
    try:
        btns = await page.query_selector_all(SELECTORS["copy_btn"])
        if btns:
            latest_btn = btns[-1]
            await latest_btn.scroll_into_view_if_needed()
            await latest_btn.click()
            await asyncio.sleep(0.5)
            text = await page.evaluate("() => navigator.clipboard.readText()")
            if text and text.strip():
                print("Retrieved clean Markdown via Copy button.")
                return text.strip()
    except Exception as e:
        print(f"(copy note: {e})")

    # Strategy 2: inner_text of latest container
    elems = await get_response_elements(page)
    if elems and len(elems) > initial_count:
        child = await elems[-1].query_selector(SELECTORS["response_content"])
        text = (await (child or elems[-1]).inner_text() or "").strip()
        if text:
            print("Retrieved text from response container.")
            return text

    raise RuntimeError("Could not retrieve Gemini response. Check debug_gemini.png if it was saved.")


# ── Top-level orchestration ───────────────────────────────────────────────────

async def execute_query(
    prompt: str,
    model: str | None = None,
    output_file: str | None = None,
    new_chat: bool = False,
    timeout: int = 300,
    list_only: bool = False,
) -> str | list:
    ensure_chrome()

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to Chrome on port {DEBUG_PORT}.\n"
                "Run launch_chrome.bat / launch_chrome.sh first, log in, then retry.\n"
                f"Detail: {e}"
            )

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        try:
            await context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass

        page = await get_or_create_gemini_page(context, new_chat=new_chat)
        await wait_for_login(page)

        if list_only:
            models = await list_models(page)
            print("\nAvailable models:\n" + "\n".join(f"  - {m}" for m in models))
            return models

        if model:
            await select_model(page, model)

        initial_count = len(await get_response_elements(page))

        try:
            await send_prompt(page, prompt)
            response_text = await wait_for_response(page, initial_count=initial_count, timeout=timeout)
        except Exception as e:
            try:
                await page.screenshot(path=str(WORKSPACE_DIR / "debug_gemini.png"))
                print("Saved diagnostic screenshot → debug_gemini.png")
            except Exception:
                pass
            raise e

        if output_file:
            out = Path(output_file).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(response_text, encoding="utf-8")
            print(f"\nResponse saved → {out}")
        else:
            print("\n" + "=" * 42 + " RESPONSE " + "=" * 42)
            print(response_text)
            print("=" * 94 + "\n")

        return response_text


# ── CLI entry-point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI-web-bridge: send a prompt to a web-based AI model via Chrome automation"
    )
    parser.add_argument("--prompt", "-p", help="Prompt text to send")
    parser.add_argument("--prompt-file", "--file", "-f", dest="file", help="File containing the prompt")
    parser.add_argument("--model", "-m", default=None, help="Model name to select (e.g. Argon, Advanced)")
    parser.add_argument("--output", "--out", "-o", dest="output", help="File to save the response into")
    parser.add_argument("--new-chat", "-n", action="store_true", help="Start a fresh chat session")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="Max seconds to wait for response")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument("--launch-only", action="store_true", help="Just open Chrome and exit")
    args = parser.parse_args()

    if args.launch_only:
        ensure_chrome()
        return

    if args.list_models:
        asyncio.run(execute_query("", list_only=True))
        return

    prompt = ""
    if args.file:
        fp = Path(args.file)
        if not fp.exists():
            sys.exit(f"Error: prompt file '{args.file}' not found.")
        prompt = fp.read_text(encoding="utf-8")
    elif args.prompt:
        prompt = args.prompt
    else:
        default_file = WORKSPACE_DIR / "prompt.txt"
        if default_file.exists():
            prompt = default_file.read_text(encoding="utf-8")
        else:
            sys.exit("Error: no prompt supplied. Use --prompt TEXT or --prompt-file FILE.")

    asyncio.run(
        execute_query(
            prompt,
            model=args.model,
            output_file=args.output,
            new_chat=args.new_chat,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
