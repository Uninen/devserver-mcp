import asyncio
import contextlib
from datetime import datetime
from typing import Any, Coroutine, Callable

from playwright.async_api import Browser, Page, Playwright

from devserver_mcp.types import Config, LogCallback


class PlaywrightManager:
    def __init__(self, config: Config, log_callback: LogCallback):
        self.config: Config = config
        self.log_callback: LogCallback = log_callback
        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.page: Page | None = None
        self.status: str = "Not Launched"
        self._status_callbacks: list[Callable[[], Coroutine[Any, Any, None]]] = []
        self._console_messages: list[str] = []

    async def _log(self, message: str, level: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            await self.log_callback("Playwright", timestamp, message)
        except Exception:
            # Log errors during callback processing if necessary, or use contextlib.suppress
            print(f"Error in log_callback: Playwright {timestamp} {message}")

    def add_status_callback(self, callback: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._status_callbacks.append(callback)

    async def _notify_status_change(self) -> None:
        for callback in self._status_callbacks:
            with contextlib.suppress(Exception):
                await callback()

    def get_status(self) -> dict[str, Any]:
        return {"status": self.status, "name": "Playwright"}

    async def _handle_console_message(self, msg: Any) -> None:
        message_text = msg.text
        self._console_messages.append(message_text)
        await self._log(f"Console: {message_text}", level="debug")

    async def launch_browser(self) -> None:
        if self.browser:
            await self._log("Browser already launched.")
            return

        self.status = "Launching..."
        await self._notify_status_change()

        try:
            from playwright.async_api import async_playwright

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            self.page.on("console", self._handle_console_message)
            self.status = "Launched"
            await self._log("Playwright browser launched successfully.")
        except Exception as e:
            self.status = f"Error: {e}"
            await self._log(f"Failed to launch Playwright browser: {e}", level="error")
        finally:
            await self._notify_status_change()

    async def close_browser(self) -> None:
        if not self.browser:
            await self._log("Browser not launched.")
            return

        self.status = "Closing..."
        await self._notify_status_change()

        try:
            if self.page:
                with contextlib.suppress(Exception): # Page might already be closed if browser crashed
                    self.page.remove_listener("console", self._handle_console_message)
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.status = "Not Launched"
            await self._log("Playwright browser closed successfully.")
        except Exception as e:
            self.status = f"Error: {e}"
            await self._log(f"Failed to close Playwright browser: {e}", level="error")
        finally:
            self.browser = None
            self.page = None
            self.playwright = None
            self._console_messages.clear()
            await self._notify_status_change()

    async def browser_navigate(self, url: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}

        await self._log(f"Navigating to {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            await self._log(f"Successfully navigated to {url}")
            return {"status": "success", "message": f"Navigated to {url}"}
        except Exception as e:
            await self._log(f"Failed to navigate to {url}: {e}", level="error")
            return {"status": "error", "message": f"Failed to navigate to {url}: {e}"}

    async def browser_snapshot(self) -> dict[str, Any]:
        if not self.page:
            return {"status": "error", "message": "Browser not launched"}

        await self._log("Capturing accessibility snapshot")
        try:
            snapshot = await self.page.accessibility.snapshot()
            await self._log("Successfully captured snapshot")
            return {"status": "success", "snapshot": snapshot}
        except Exception as e:
            await self._log(f"Failed to capture snapshot: {e}", level="error")
            return {"status": "error", "message": f"Failed to capture snapshot: {e}"}

    async def browser_console_messages(self) -> dict[str, Any]:
        if not self.page: # Check for page, as console messages are tied to a page context
            return {"status": "error", "message": "Browser not launched or no active page"}

        await self._log("Retrieving console messages")
        # Return a copy of the current messages. Messages are cleared when the browser is closed.
        messages_copy = list(self._console_messages)
        return {"status": "success", "messages": messages_copy}

    async def ensure_launched(self) -> bool:
        """Helper to launch browser if not already launched. Returns True if successful or already launched."""
        if not self.browser or not self.page:
            await self.launch_browser()
        return self.status == "Launched"

    async def get_page_content(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
             return {"status": "error", "message": "Browser not launched"}
        try:
            content = await self.page.content()
            return {"status": "success", "content": content}
        except Exception as e:
            await self._log(f"Failed to get page content: {e}", level="error")
            return {"status": "error", "message": f"Failed to get page content: {e}"}

    async def run_javascript(self, script: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            result = await self.page.evaluate(script)
            return {"status": "success", "result": result}
        except Exception as e:
            await self._log(f"Failed to run javascript: {e}", level="error")
            return {"status": "error", "message": f"Failed to run javascript: {e}"}

    async def click_element(self, selector: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.click(selector)
            return {"status": "success", "message": f"Clicked element with selector '{selector}'"}
        except Exception as e:
            await self._log(f"Failed to click element with selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to click element with selector '{selector}': {e}"}

    async def type_into_element(self, selector: str, text: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.type(selector, text)
            return {"status": "success", "message": f"Typed '{text}' into element with selector '{selector}'"}
        except Exception as e:
            await self._log(f"Failed to type into element with selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to type into element with selector '{selector}': {e}"}

    async def get_element_attributes(self, selector: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            element = await self.page.query_selector(selector)
            if not element:
                return {"status": "error", "message": f"Element with selector '{selector}' not found"}

            attributes = await element.evaluate("element => Array.from(element.attributes).reduce((obj, attr) => { obj[attr.name] = attr.value; return obj; }, {})")
            return {"status": "success", "attributes": attributes}
        except Exception as e:
            await self._log(f"Failed to get attributes for element with selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to get attributes for element with selector '{selector}': {e}"}

    async def get_element_text(self, selector: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            text_content = await self.page.text_content(selector)
            return {"status": "success", "text_content": text_content}
        except Exception as e:
            await self._log(f"Failed to get text for element with selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to get text for element with selector '{selector}': {e}"}

    async def get_element_html(self, selector: str) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            html_content = await self.page.inner_html(selector)
            return {"status": "success", "html_content": html_content}
        except Exception as e:
            await self._log(f"Failed to get HTML for element with selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to get HTML for element with selector '{selector}': {e}"}

    async def wait_for_selector(self, selector: str, timeout: float | None = None) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return {"status": "success", "message": f"Element with selector '{selector}' is visible"}
        except Exception as e:
            await self._log(f"Failed to wait for selector '{selector}': {e}", level="error")
            return {"status": "error", "message": f"Failed to wait for selector '{selector}': {e}"}

    async def take_screenshot(self, path: str | None = None) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            screenshot_bytes = await self.page.screenshot(path=path)
            if path:
                return {"status": "success", "message": f"Screenshot saved to {path}"}
            else:
                # If no path, screenshot_bytes contains the image
                # For now, let's just confirm it was taken if not saved to path
                return {"status": "success", "message": "Screenshot taken", "screenshot_bytes_length": len(screenshot_bytes or b"")}

        except Exception as e:
            await self._log(f"Failed to take screenshot: {e}", level="error")
            return {"status": "error", "message": f"Failed to take screenshot: {e}"}

    async def set_viewport_size(self, width: int, height: int) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.set_viewport_size({"width": width, "height": height})
            return {"status": "success", "message": f"Viewport size set to {width}x{height}"}
        except Exception as e:
            await self._log(f"Failed to set viewport size: {e}", level="error")
            return {"status": "error", "message": f"Failed to set viewport size: {e}"}

    async def scroll_page(self, x: int, y: int) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.evaluate(f"window.scrollTo({x}, {y})")
            return {"status": "success", "message": f"Scrolled page to {x},{y}"}
        except Exception as e:
            await self._log(f"Failed to scroll page: {e}", level="error")
            return {"status": "error", "message": f"Failed to scroll page: {e}"}

    async def get_current_url(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            current_url = self.page.url
            return {"status": "success", "url": current_url}
        except Exception as e: # Should not happen for page.url but good practice
            await self._log(f"Failed to get current URL: {e}", level="error")
            return {"status": "error", "message": f"Failed to get current URL: {e}"}

    async def go_back(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.go_back()
            return {"status": "success", "message": "Navigated back"}
        except Exception as e:
            await self._log(f"Failed to go back: {e}", level="error")
            return {"status": "error", "message": f"Failed to go back: {e}"}

    async def go_forward(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.go_forward()
            return {"status": "success", "message": "Navigated forward"}
        except Exception as e:
            await self._log(f"Failed to go forward: {e}", level="error")
            return {"status": "error", "message": f"Failed to go forward: {e}"}

    async def reload_page(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.page:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.page.reload()
            return {"status": "success", "message": "Page reloaded"}
        except Exception as e:
            await self._log(f"Failed to reload page: {e}", level="error")
            return {"status": "error", "message": f"Failed to reload page: {e}"}

    async def get_cookies(self, urls: list[str] | None = None) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.browser: # Check browser context for cookies
            return {"status": "error", "message": "Browser not launched"}
        try:
            cookies = await self.browser.contexts[0].cookies(urls=urls)
            return {"status": "success", "cookies": cookies}
        except Exception as e:
            await self._log(f"Failed to get cookies: {e}", level="error")
            return {"status": "error", "message": f"Failed to get cookies: {e}"}

    async def add_cookies(self, cookies: list[dict[str, Any]]) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.browser:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.browser.contexts[0].add_cookies(cookies)
            return {"status": "success", "message": "Cookies added"}
        except Exception as e:
            await self._log(f"Failed to add cookies: {e}", level="error")
            return {"status": "error", "message": f"Failed to add cookies: {e}"}

    async def clear_cookies(self) -> dict[str, Any]:
        if not await self.ensure_launched() or not self.browser:
            return {"status": "error", "message": "Browser not launched"}
        try:
            await self.browser.contexts[0].clear_cookies()
            return {"status": "success", "message": "Cookies cleared"}
        except Exception as e:
            await self._log(f"Failed to clear cookies: {e}", level="error")
            return {"status": "error", "message": f"Failed to clear cookies: {e}"}

    async def clear_console_messages(self) -> dict[str, Any]:
        self._console_messages.clear()
        await self._log("Console messages cleared.")
        return {"status": "success", "message": "Console messages cleared"}
