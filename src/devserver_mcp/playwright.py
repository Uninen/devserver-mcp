import json
from typing import TYPE_CHECKING, Any, Literal

from devserver_mcp.log_storage import LogStorage

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page, Playwright

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None


class PlaywrightOperator:
    @classmethod
    def check_availability(cls) -> tuple[bool, str | None]:
        if not PLAYWRIGHT_AVAILABLE:
            return (
                False,
                "Playwright module not installed. Please install Playwright \
                    package (uv add playwright && playwright install)",
            )
        return True, None

    def __init__(self, browser_type: str = "chromium", headless: bool = True, **browser_kwargs: Any) -> None:
        self.browser_type = browser_type
        self.headless = headless
        self.browser_kwargs = browser_kwargs

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._console_messages: LogStorage = LogStorage(max_lines=10000)

        self._initialized = False

    async def _initialize(self) -> None:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright module not installed. Please run: pip install \
                    playwright && playwright install"
            )

        try:
            self._playwright = await async_playwright().start()  # type: ignore

            if self.browser_type == "chromium":
                launcher = self._playwright.chromium
            elif self.browser_type == "firefox":
                launcher = self._playwright.firefox
            elif self.browser_type == "webkit":
                launcher = self._playwright.webkit
            else:
                raise ValueError(f"Unsupported browser type: {self.browser_type}")

            self._browser = await launcher.launch(headless=self.headless, **self.browser_kwargs)

            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

            self._page.on("console", self._handle_console_message)

            self._initialized = True

        except Exception as e:
            await self.close()
            raise RuntimeError(f"Failed to initialize Playwright: {e}") from e

    def _handle_console_message(self, msg: Any) -> None:
        message_data = {
            "type": msg.type,
            "text": msg.text,
            "args": [str(arg) for arg in msg.args],
            "location": {
                "url": msg.location.get("url") if msg.location else None,
                "line": msg.location.get("lineNumber") if msg.location else None,
                "column": msg.location.get("columnNumber") if msg.location else None,
            },
        }
        self._console_messages.append(json.dumps(message_data))

    async def navigate(
        self,
        url: str,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] | None = "networkidle",
    ) -> dict[str, Any]:
        if not self._page:
            raise RuntimeError("Playwright not properly initialized")

        try:
            response = await self._page.goto(url, wait_until=wait_until)

            return {
                "url": self._page.url,
                "title": await self._page.title(),
                "status": response.status if response else None,
                "ok": response.ok if response else None,
            }
        except Exception as e:
            raise RuntimeError(f"Navigation to {url} failed: {e}") from e

    async def snapshot(self) -> dict[str, Any]:
        if not self._page:
            raise RuntimeError("Playwright not properly initialized")

        try:
            snapshot = await self._page.accessibility.snapshot()

            return {
                "url": self._page.url,
                "title": await self._page.title(),
                "snapshot": snapshot,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to capture accessibility snapshot: {e}") from e

    async def get_console_messages(
        self, clear: bool = False, offset: int = 0, limit: int = 100, reverse: bool = True
    ) -> tuple[list[dict[str, Any]], int, bool]:
        raw_messages, total, has_more = self._console_messages.get_range(offset, limit, reverse)
        messages = [json.loads(msg) for msg in raw_messages]

        if clear:
            self._console_messages.clear()

        return messages, total, has_more

    async def click(self, ref: str) -> dict[str, Any]:
        if not self._page:
            raise RuntimeError("Playwright not properly initialized")

        try:
            await self._page.click(ref)

            return {
                "status": "success",
                "message": f"Clicked element: {ref}",
                "url": self._page.url,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to click element {ref}: {e}") from e

    async def type(self, ref: str, text: str, submit: bool = False, slowly: bool = False) -> dict[str, Any]:
        if not self._page:
            raise RuntimeError("Playwright not properly initialized")

        try:
            if slowly:
                await self._page.type(ref, text)
            else:
                await self._page.fill(ref, text)

            if submit:
                await self._page.press(ref, "Enter")

            return {
                "status": "success",
                "message": f"Typed text into element: {ref}",
                "text": text,
                "url": self._page.url,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to type into element {ref}: {e}") from e

    async def close(self) -> None:
        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        except Exception:
            pass

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def current_url(self) -> str | None:
        return self._page.url if self._page else None

    async def initialize(self) -> None:
        if not self._initialized:
            await self._initialize()

    async def __aenter__(self):
        if not self._initialized:
            await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
