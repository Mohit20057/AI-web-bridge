"""Gemini web UI adapter."""

import asyncio
import time

from .base import (
    LoginRequiredError,
    ModelUnavailableError,
    ProviderAdapter,
    ResponseExtractionError,
    ResponseTimeoutError,
    SelectorMismatchError,
    validate_chat_url,
)


class GeminiProvider(ProviderAdapter):
    async def close(self) -> None:
        # The attached browser and its signed-in profile belong to the user.
        return None

    async def open_or_resume_chat(self, context, chat_url: str | None = None, new_chat: bool = False):
        chat_url = validate_chat_url(chat_url, self.url)
        page = next((p for p in context.pages if "gemini.google.com" in p.url), None)
        if page is None:
            page = await context.new_page()
            await page.goto(self.url)
            if chat_url and not new_chat:
                await page.goto(chat_url)
        else:
            await page.bring_to_front()
            if new_chat:
                await self.start_new_chat(page)
            elif chat_url and page.url != chat_url:
                await page.goto(chat_url)
        return page

    async def wait_for_login(self, page, timeout: int = 120) -> None:
        print("Checking Gemini authentication status…")
        deadline = time.time() + timeout
        while time.time() < deadline:
            elem = await page.query_selector(self.selectors["input"])
            if elem and await elem.is_visible():
                return
            if "accounts.google.com" in page.url:
                print("⚠  Not signed in. Please log into Google in the opened browser window.")
            await asyncio.sleep(2)
        raise LoginRequiredError(
            "Timed out waiting for Gemini's signed-in chat interface. "
            "Sign in to Google in the bridge browser and retry."
        )

    async def start_new_chat(self, page) -> None:
        try:
            btn = await page.query_selector(self.selectors["new_chat"])
            if btn and await btn.is_visible():
                print("Starting a new chat session…")
                await btn.click()
                await asyncio.sleep(1.5)
        except Exception as exc:
            print(f"(new chat note: {exc})")

    async def list_models(self, page) -> list[str]:
        try:
            btn = await page.query_selector(self.selectors["model_btn"])
            if not btn or not await btn.is_visible():
                return []
            await btn.click()
            await asyncio.sleep(1)
            items = await page.query_selector_all(self.selectors["menu_item"])
            models = [
                " ".join((await item.inner_text() or "").split())
                for item in items
                if await item.is_visible()
            ]
            await page.keyboard.press("Escape")
            return [model for model in models if model]
        except Exception:
            return []

    async def select_model(self, page, model_name: str) -> str:
        print(f"Selecting model '{model_name}'…")
        btn = await page.query_selector(self.selectors["model_btn"])
        if not btn or not await btn.is_visible():
            raise SelectorMismatchError("Could not find Gemini's model picker in the current page.")

        current = (await btn.inner_text() or "").strip()
        if model_name.casefold().strip() == current.casefold():
            print(f"  Already active: {current}")
            return current

        await btn.click()
        await asyncio.sleep(1)
        options = []
        for option in await page.query_selector_all(self.selectors["menu_item"]):
            if await option.is_visible():
                label = " ".join((await option.inner_text() or "").split())
                if label:
                    options.append((label, option))
        target = model_name.casefold().strip()
        exact = [(label, option) for label, option in options if label.casefold() == target]
        matches = exact or [(label, option) for label, option in options if target in label.casefold()]
        if len(matches) > 1:
            await page.keyboard.press("Escape")
            choices = "; ".join(label for label, _ in matches)
            raise ModelUnavailableError(
                f"'{model_name}' matches multiple Gemini choices: {choices}. "
                "Use a more specific label from --list-models."
            )
        if matches:
            label, option = matches[0]
            await option.click()
            await asyncio.sleep(1)
            refreshed = await page.query_selector(self.selectors["model_btn"])
            active = (await refreshed.inner_text() or "").strip() if refreshed else ""
            if target not in active.casefold():
                raise ModelUnavailableError(
                    f"Gemini did not confirm '{model_name}' as the active model. "
                    "Choose a model shown in Gemini's picker and retry."
                )
            print(f"  Active model: {active}")
            return active

        await page.keyboard.press("Escape")
        choices = "; ".join(label for label, _ in options)
        if not choices:
            raise SelectorMismatchError("Gemini's model menu opened, but no model choices were detected.")
        raise ModelUnavailableError(
            f"Gemini model '{model_name}' was not found in the visible menu. Available choices: {choices}."
        )

    async def get_response_elements(self, page):
        for key in ("response_container", "response_content"):
            elements = await page.query_selector_all(self.selectors[key])
            if elements:
                return elements
        return []

    async def send_prompt(self, page, prompt_text: str) -> None:
        print("Locating prompt input…")
        try:
            input_elem = await page.wait_for_selector(self.selectors["input"], timeout=10_000)
        except Exception as exc:
            raise SelectorMismatchError(
                "Cannot find Gemini's prompt input. Check that the page is loaded and signed in."
            ) from exc
        if not input_elem:
            raise SelectorMismatchError("Cannot find Gemini's prompt input.")

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

        for selector in self.selectors["send_btn"].split(", "):
            btn = await page.query_selector(selector.strip())
            if btn and await btn.is_visible() and await btn.is_enabled():
                await btn.click()
                print("Clicked Send button.")
                return
        print("Send button not found; pressing Enter…")
        await input_elem.press("Enter")

    async def wait_for_response(self, page, initial_count: int = 0, timeout: int = 300) -> str:
        """Wait for a new response to finish, then extract it as text."""
        print(f"Waiting for new response (baseline: {initial_count} message(s))…")
        deadline = time.time() + timeout
        started = False

        while time.time() < deadline:
            stop = await page.query_selector(self.selectors["stop_btn"])
            if stop and await stop.is_visible():
                started = True
                break
            if len(await self.get_response_elements(page)) > initial_count:
                started = True
                break
            await asyncio.sleep(0.5)

        if not started:
            raise ResponseTimeoutError("Gemini did not start a response before the timeout.")

        print("Gemini is generating…")
        last_text, stable_since = "", time.time()
        stable_seconds = float(self.config.get("timeouts", {}).get("response_stable_seconds", 2.5))
        completed = False
        while time.time() < deadline:
            stop = await page.query_selector(self.selectors["stop_btn"])
            generating = stop is not None and await stop.is_visible()
            elements = await self.get_response_elements(page)
            if len(elements) > initial_count:
                try:
                    current = (await elements[-1].inner_text() or "").strip()
                except Exception:
                    current = ""
                if current != last_text:
                    last_text, stable_since = current, time.time()
                elif not generating and current and time.time() - stable_since >= stable_seconds:
                    print("Generation complete.")
                    completed = True
                    break
            await asyncio.sleep(0.8)

        if not completed:
            raise ResponseTimeoutError(f"Gemini did not finish its response within {timeout} seconds.")

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.0)

        try:
            buttons = await page.query_selector_all(self.selectors["copy_btn"])
            if buttons:
                await buttons[-1].scroll_into_view_if_needed()
                await buttons[-1].click()
                await asyncio.sleep(0.5)
                text = await page.evaluate("() => navigator.clipboard.readText()")
                if text and text.strip():
                    print("Retrieved clean Markdown via Copy button.")
                    return text.strip()
        except Exception as exc:
            print(f"(copy note: {exc})")

        elements = await self.get_response_elements(page)
        if elements and len(elements) > initial_count:
            child = await elements[-1].query_selector(self.selectors["response_content"])
            text = (await (child or elements[-1]).inner_text() or "").strip()
            if text:
                print("Retrieved text from response container.")
                return text

        raise ResponseExtractionError(
            "Gemini generated a response, but the bridge could not extract it. "
            "Check the saved diagnostic screenshot and update the Gemini selectors if needed."
        )
