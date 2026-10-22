"""Shared DOM-driven chat behavior for web providers with configurable selectors."""

import asyncio
import time
from urllib.parse import urlsplit

from .base import (
    LoginRequiredError,
    ModelUnavailableError,
    ProviderAdapter,
    ResponseExtractionError,
    ResponseTimeoutError,
    SelectorMismatchError,
    validate_chat_url,
)


class SelectorChatProvider(ProviderAdapter):
    """Common chat flow; each provider supplies its own URL and selectors."""

    async def close(self) -> None:
        # The attached browser and its signed-in profile belong to the user.
        return None

    async def open_or_resume_chat(self, context, chat_url: str | None = None, new_chat: bool = False):
        chat_url = validate_chat_url(chat_url, self.url)
        hostname = urlsplit(self.url).hostname or ""
        page = next(
            (
                item
                for item in context.pages
                if (current_host := (urlsplit(item.url).hostname or "")) == hostname
                or current_host.endswith(f".{hostname}")
            ),
            None,
        )
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

    async def start_new_chat(self, page) -> None:
        selector = self.selectors.get("new_chat")
        if selector:
            button = await page.query_selector(selector)
            if button and await button.is_visible():
                await button.click()
                await asyncio.sleep(1)
                return
        await page.goto(self.url)

    async def wait_for_login(self, page, timeout: int = 120) -> None:
        print(f"Checking {self.name} authentication status…")
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                element = await page.query_selector(self.selectors["input"])
                if element and await element.is_visible():
                    return
            except Exception:
                pass
            await asyncio.sleep(2)
        login_hint = self.config.get("login_hint", "sign in to your account in the bridge browser")
        raise LoginRequiredError(
            f"Timed out waiting for {self.name}'s chat input. Please {login_hint}, then retry."
        )

    async def list_models(self, page) -> list[str]:
        picker = self.selectors.get("model_btn")
        if not picker:
            return []
        button = await page.query_selector(picker)
        if not button or not await button.is_visible():
            return []
        try:
            await button.click()
            await asyncio.sleep(0.4)
            labels = []
            for item in await page.query_selector_all(self.selectors["menu_item"]):
                if not await item.is_visible():
                    continue
                label = " ".join((await item.inner_text() or "").split())
                if label and label not in labels:
                    labels.append(label)
            await page.keyboard.press("Escape")
            return labels
        except Exception:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            return []

    async def select_model(self, page, model_name: str) -> str:
        picker = self.selectors.get("model_btn")
        if not picker:
            raise SelectorMismatchError(f"{self.name} model picker is not configured.")
        button = await page.query_selector(picker)
        if not button or not await button.is_visible():
            raise SelectorMismatchError(f"Could not find {self.name}'s visible model picker.")

        current = " ".join((await button.inner_text() or "").split())
        if model_name.casefold().strip() == current.casefold():
            return current

        await button.click()
        await asyncio.sleep(0.4)
        options = []
        for element in await page.query_selector_all(self.selectors["menu_item"]):
            if await element.is_visible():
                label = " ".join((await element.inner_text() or "").split())
                if label:
                    options.append((label, element))

        target = model_name.casefold().strip()
        exact = [(label, element) for label, element in options if label.casefold() == target]
        matches = exact or [(label, element) for label, element in options if target in label.casefold()]
        if len(matches) > 1:
            await page.keyboard.press("Escape")
            choices = "; ".join(label for label, _ in matches)
            raise ModelUnavailableError(
                f"'{model_name}' matches multiple {self.name} choices: {choices}. "
                "Use a more specific label from --list-models."
            )
        if not matches:
            await page.keyboard.press("Escape")
            choices = "; ".join(label for label, _ in options)
            if not choices:
                raise SelectorMismatchError(
                    f"{self.name}'s model menu opened, but no model choices were detected."
                )
            raise ModelUnavailableError(
                f"'{model_name}' is not available in {self.name}'s visible model menu. "
                f"Available choices: {choices}."
            )

        label, option = matches[0]
        await option.click()
        await asyncio.sleep(0.7)
        refreshed = await page.query_selector(picker)
        active = " ".join((await refreshed.inner_text() or "").split()) if refreshed else ""
        if target not in active.casefold():
            raise ModelUnavailableError(
                f"{self.name} did not confirm '{model_name}' as the active model "
                f"after selecting '{label}'. Check the visible picker and retry."
            )
        print(f"Active {self.name} model: {active}")
        return active

    async def get_response_elements(self, page):
        elements = await page.query_selector_all(self.selectors["response_container"])
        return [element for element in elements if await element.is_visible()]

    async def send_prompt(self, page, prompt_text: str) -> None:
        try:
            input_element = await page.wait_for_selector(self.selectors["input"], timeout=10_000, state="visible")
        except Exception as exc:
            raise SelectorMismatchError(
                f"Cannot find {self.name}'s prompt input. Its UI may have changed; update this provider's selectors."
            ) from exc
        if not input_element:
            raise SelectorMismatchError(f"Cannot find {self.name}'s prompt input.")

        await input_element.scroll_into_view_if_needed()
        await input_element.click()
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.insert_text(prompt_text)

        for selector in self.selectors["send_btn"].split(", "):
            button = await page.query_selector(selector.strip())
            if button and await button.is_visible() and await button.is_enabled():
                await button.click()
                return
        await input_element.press("Enter")

    async def wait_for_response(self, page, initial_count: int = 0, timeout: int = 300) -> str:
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
            raise ResponseTimeoutError(f"{self.name} did not start a response before the timeout.")

        stable_seconds = float(self.config.get("timeouts", {}).get("response_stable_seconds", 2.5))
        last_text, stable_since, completed = "", time.time(), False
        while time.time() < deadline:
            stop = await page.query_selector(self.selectors["stop_btn"])
            generating = stop is not None and await stop.is_visible()
            elements = await self.get_response_elements(page)
            if len(elements) > initial_count:
                current = (await elements[-1].inner_text() or "").strip()
                if current != last_text:
                    last_text, stable_since = current, time.time()
                elif current and not generating and time.time() - stable_since >= stable_seconds:
                    completed = True
                    break
            await asyncio.sleep(0.7)
        if not completed:
            raise ResponseTimeoutError(f"{self.name} did not finish its response within {timeout} seconds.")

        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        content_selector = self.selectors.get("response_content")
        elements = await self.get_response_elements(page)
        if elements and len(elements) > initial_count:
            response = elements[-1]
            content = await response.query_selector(content_selector) if content_selector else None
            text = (await (content or response).inner_text() or "").strip()
            if text:
                return text
        raise ResponseExtractionError(
            f"{self.name} finished generating, but the bridge could not read the response. "
            "The provider's response selectors may need updating."
        )
