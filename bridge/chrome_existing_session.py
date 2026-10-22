"""Small Playwright-shaped adapter over Google's user-approved Chrome MCP session."""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit

from providers.base import BrowserUnavailableError


class ChromeDevToolsSession:
    """Own one Chrome DevTools MCP process and keep page output out of model context."""

    def __init__(self):
        self.process = None
        self._request_id = 0
        self._lock = asyncio.Lock()

    async def start(self):
        executable = shutil.which("npx") or shutil.which("npx.cmd")
        if not executable:
            raise BrowserUnavailableError(
                "Chrome existing-session mode needs Node.js/npm (npx). Install the current Node.js LTS, "
                "then run the bridge again."
            )
        command = [
            executable,
            "--yes",
            "chrome-devtools-mcp@latest",
            "--autoConnect",
            "--no-usage-statistics",
            "--no-performance-crux",
        ]
        env = os.environ.copy()
        env["CHROME_DEVTOOLS_MCP_NO_USAGE_STATISTICS"] = "1"
        env["CHROME_DEVTOOLS_MCP_NO_UPDATE_CHECKS"] = "1"
        if sys.platform == "win32" and executable.casefold().endswith((".cmd", ".bat")):
            command = ["cmd.exe", "/d", "/c", "call", *command]
        try:
            self.process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            initialized = await self._request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-web-bridge", "version": "1.0"},
            }, timeout=90)
            if not isinstance(initialized, dict) or "serverInfo" not in initialized:
                raise BrowserUnavailableError("Chrome DevTools MCP did not complete its startup handshake.")
            await self._notify("notifications/initialized", {})
            print(
                "Connecting to your existing Chrome session. Chrome may show a Remote Debugging approval dialog; "
                "review it and click Allow to continue."
            )
            await self.call_tool("list_pages", {}, timeout=180)
        except Exception:
            await self.close()
            raise
        return self

    async def _read_response(self, request_id: int, timeout: int):
        if not self.process or not self.process.stdout:
            raise BrowserUnavailableError("Chrome DevTools MCP is not running.")
        while True:
            try:
                raw = await asyncio.wait_for(self.process.stdout.readline(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise BrowserUnavailableError(
                    "Timed out waiting for Chrome. Enable Remote Debugging at "
                    "chrome://inspect/#remote-debugging and approve the connection in Chrome."
                ) from exc
            if not raw:
                code = self.process.returncode
                raise BrowserUnavailableError(
                    f"Chrome DevTools MCP stopped before replying (exit {code}). Check Node.js/npm and Chrome."
                )
            try:
                message = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                detail = message["error"].get("message", "unknown MCP error")
                raise BrowserUnavailableError(f"Chrome DevTools MCP error: {detail}")
            return message.get("result", {})

    async def _request(self, method: str, params: dict, timeout: int = 60):
        async with self._lock:
            if not self.process or not self.process.stdin:
                raise BrowserUnavailableError("Chrome DevTools MCP is not running.")
            self._request_id += 1
            request_id = self._request_id
            payload = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            self.process.stdin.write((payload + "\n").encode("utf-8"))
            await self.process.stdin.drain()
            return await self._read_response(request_id, timeout)

    async def _notify(self, method: str, params: dict):
        if self.process and self.process.stdin:
            payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
            self.process.stdin.write((payload + "\n").encode("utf-8"))
            await self.process.stdin.drain()

    async def call_tool(self, name: str, arguments: dict, timeout: int = 60) -> dict:
        result = await self._request("tools/call", {"name": name, "arguments": arguments}, timeout=timeout)
        if result.get("isError"):
            raise BrowserUnavailableError(_result_text(result) or f"Chrome tool '{name}' failed.")
        return result

    async def pages(self) -> list[dict]:
        result = await self.call_tool("list_pages", {})
        pages = []
        for item in (result.get("structuredContent") or {}).get("pages", []):
            if isinstance(item, dict) and isinstance(item.get("id"), (str, int)):
                pages.append({"id": int(item["id"]), "url": str(item.get("url") or ""), "title": str(item.get("title") or "")})
        if pages:
            return pages
        for line in _result_text(result).splitlines():
            match = re.match(r"\s*(\d+):\s*(.*?)\s+\((https?://[^)]*)\)", line)
            if match:
                pages.append({"id": int(match.group(1)), "title": match.group(2), "url": match.group(3)})
        return pages

    async def new_page(self, url: str):
        before = {item["id"] for item in await self.pages()}
        await self.call_tool("new_page", {"url": url}, timeout=90)
        for page in await self.pages():
            if page["id"] not in before and _same_host(page["url"], url):
                return ChromeMcpPage(self, page["id"], page["url"])
        candidates = [page for page in await self.pages() if _same_host(page["url"], url)]
        if candidates:
            page = candidates[-1]
            return ChromeMcpPage(self, page["id"], page["url"])
        raise BrowserUnavailableError("Chrome opened a tab, but the bridge could not identify it.")

    async def close(self):
        process, self.process = self.process, None
        if not process or process.returncode is not None:
            return
        try:
            process.stdin.close()
            await asyncio.wait_for(process.wait(), timeout=3)
        except Exception:
            process.kill()
            try:
                await process.wait()
            except Exception:
                pass


def _result_text(result: dict) -> str:
    content = result.get("content", [])
    return "\n".join(item.get("text", "") for item in content if item.get("type") == "text")


def _result_value(result: dict):
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        for key in ("result", "value", "output"):
            if key in structured:
                return structured[key]
    text = _result_text(result)
    match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
    if match:
        if match.group(1).strip() == "undefined":
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    raise BrowserUnavailableError("Chrome returned an unreadable page result.")


def _same_host(left: str, right: str) -> bool:
    return (urlsplit(left).hostname or "").casefold() == (urlsplit(right).hostname or "").casefold()


def _selector_candidates(selector: str) -> list[dict]:
    candidates = []
    for part in selector.split(", "):
        text_match = re.fullmatch(r"(.+?):has-text\(['\"](.+?)['\"]\)", part.strip())
        if text_match:
            candidates.append({"css": text_match.group(1), "text": text_match.group(2)})
        else:
            candidates.append({"css": part.strip(), "text": None})
    return candidates


class ChromeMcpPage:
    def __init__(self, session: ChromeDevToolsSession, page_id: int, url: str):
        self.session = session
        self.page_id = page_id
        self.url = url
        self.keyboard = ChromeMcpKeyboard(self)

    async def _evaluate(self, function: str):
        source = function.strip()
        if "=>" not in source and not source.startswith("function"):
            function = f"() => {{ {source} }}"
        result = await self.session.call_tool("evaluate_script", {
            "pageId": self.page_id,
            "function": function,
            "waitForStableDom": False,
        })
        return _result_value(result)

    async def goto(self, url: str):
        await self.session.call_tool("navigate_page", {"pageId": self.page_id, "type": "url", "url": url}, timeout=90)
        self.url = url

    async def refresh_url(self):
        current = await self._evaluate("() => location.href")
        if isinstance(current, str):
            self.url = current
        return self.url

    async def bring_to_front(self):
        await self.session.call_tool("select_page", {"pageId": self.page_id, "bringToFront": True})

    async def query_selector_all(self, selector: str):
        candidates = json.dumps(_selector_candidates(selector), ensure_ascii=False)
        count = await self._evaluate(
            f"""() => {{ const c={candidates}, all=[]; for (const x of c) {{ let e=[]; try {{ e=[...document.querySelectorAll(x.css)]; }} catch {{}} if (x.text) e=e.filter(n => (n.innerText||n.textContent||'').includes(x.text)); for (const n of e) if (!all.includes(n)) all.push(n); }} return all.length; }}"""
        )
        return [ChromeMcpElement(self, selector, i) for i in range(int(count or 0))]

    async def query_selector(self, selector: str):
        elements = await self.query_selector_all(selector)
        return elements[0] if elements else None

    async def wait_for_selector(self, selector: str, timeout: int = 30000, state: str = "visible"):
        deadline = asyncio.get_running_loop().time() + timeout / 1000
        while asyncio.get_running_loop().time() < deadline:
            element = await self.query_selector(selector)
            if element and (state != "visible" or await element.is_visible()):
                return element
            await asyncio.sleep(0.25)
        raise TimeoutError(f"Timed out waiting for selector: {selector}")

    async def evaluate(self, expression: str, args=None):
        if args and isinstance(args, list) and isinstance(args[0], ChromeMcpElement):
            element = args[0]
            if len(args) > 1 and isinstance(args[1], str):
                await element.fill(args[1])
            else:
                await element.dispatch_input_events()
            return None
        return await self._evaluate(expression)

    async def screenshot(self, *args, **kwargs):
        raise BrowserUnavailableError("Chrome DevTools MCP does not return diagnostic screenshots as local files.")


class ChromeMcpKeyboard:
    def __init__(self, page: ChromeMcpPage):
        self.page = page

    async def press(self, key: str):
        await self.page.session.call_tool("press_key", {"pageId": self.page.page_id, "key": key})

    async def insert_text(self, text: str):
        await self.page.session.call_tool("type_text", {"pageId": self.page.page_id, "text": text})


class ChromeMcpElement:
    def __init__(self, page: ChromeMcpPage, selector: str, index: int, child: str | None = None):
        self.page = page
        self.selector = selector
        self.index = index
        self.child = child

    def _element_expression(self, operation: str, argument=None):
        candidates = json.dumps(_selector_candidates(self.selector), ensure_ascii=False)
        child = json.dumps(self.child, ensure_ascii=False)
        arg = json.dumps(argument, ensure_ascii=False)
        return f"""() => {{ const c={candidates}, all=[]; for (const x of c) {{ let e=[]; try {{ e=[...document.querySelectorAll(x.css)]; }} catch {{}} if (x.text) e=e.filter(n => (n.innerText||n.textContent||'').includes(x.text)); for (const n of e) if (!all.includes(n)) all.push(n); }} let e=all[{self.index}]; if (!e) return null; const child={child}; if (child) e=e.querySelector(child); if (!e) return null; const op={json.dumps(operation)}; if(op==='text') return e.innerText ?? e.textContent ?? ''; if(op==='visible') {{ const r=e.getBoundingClientRect(), s=getComputedStyle(e); return !!(r.width||r.height) && s.visibility!=='hidden' && s.display!=='none'; }} if(op==='enabled') return !e.disabled; if(op==='click') {{ e.click(); return true; }} if(op==='focus') {{ e.focus(); return true; }} if(op==='scroll') {{ e.scrollIntoView({{block:'center'}}); return true; }} if(op==='fill') {{ e.focus(); if('value' in e) e.value={arg}; else e.innerText={arg}; e.dispatchEvent(new InputEvent('input',{{bubbles:true,inputType:'insertText',data:{arg}}})); e.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} if(op==='input') {{ e.dispatchEvent(new Event('input',{{bubbles:true}})); e.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return null; }}"""

    async def inner_text(self):
        return await self.page._evaluate(self._element_expression("text")) or ""

    async def is_visible(self):
        return bool(await self.page._evaluate(self._element_expression("visible")))

    async def is_enabled(self):
        return bool(await self.page._evaluate(self._element_expression("enabled")))

    async def click(self):
        await self.page._evaluate(self._element_expression("click"))

    async def focus(self):
        await self.page._evaluate(self._element_expression("focus"))

    async def scroll_into_view_if_needed(self):
        await self.page._evaluate(self._element_expression("scroll"))

    async def fill(self, text: str):
        await self.page._evaluate(self._element_expression("fill", text))

    async def dispatch_input_events(self):
        await self.page._evaluate(self._element_expression("input"))

    async def press(self, key: str):
        await self.focus()
        await self.page.keyboard.press(key)

    async def query_selector(self, selector: str):
        escaped = json.dumps(selector, ensure_ascii=False)
        if await self.page._evaluate(self._element_expression("text")) is None:
            return None
        parent_selector = self.selector
        result = await self.page._evaluate(
            f"""() => {{ const c={json.dumps(_selector_candidates(parent_selector), ensure_ascii=False)}, all=[]; for (const x of c) {{ let e=[]; try {{ e=[...document.querySelectorAll(x.css)]; }} catch {{}} if(x.text)e=e.filter(n=>(n.innerText||n.textContent||'').includes(x.text)); for(const n of e)if(!all.includes(n))all.push(n); }} return !!all[{self.index}]?.querySelector({escaped}); }}"""
        )
        return ChromeMcpElement(self.page, self.selector, self.index, selector) if result else None


class ChromeMcpContext:
    def __init__(self, session: ChromeDevToolsSession, provider_url: str):
        self.session = session
        self.provider_url = provider_url
        self.pages = []

    async def initialize_pages(self):
        self.pages = [
            ChromeMcpPage(self.session, item["id"], item["url"])
            for item in await self.session.pages()
            if item["url"].startswith(("http://", "https://"))
        ]
        return self

    async def new_page(self):
        page = await self.session.new_page(self.provider_url)
        self.pages.append(page)
        return page

    async def grant_permissions(self, *_args, **_kwargs):
        # Chrome DevTools MCP uses the permission granted in Chrome itself.
        return None
