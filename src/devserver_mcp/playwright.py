"""
Playwright operator for MCP server functionality.

This module provides a PlaywrightOperator class that manages a Playwright instance
for use within the MCP server, handling browser operations like navigation,
snapshots, and console message collection.
"""

import asyncio
from typing import Any, Literal

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class PlaywrightOperator:
    """
    A helper class to control a Playwright instance for MCP server operations.

    Manages a single browser instance and provides methods for navigation,
    accessibility snapshots, and console message collection.
    """

    def __init__(self, browser_type: str = "chromium", headless: bool = True, **browser_kwargs: Any) -> None:
        """
        Initialize the PlaywrightOperator.

        Args:
            browser_type: Browser type to use (chromium, firefox, webkit)
            headless: Whether to run browser in headless mode
            **browser_kwargs: Additional arguments to pass to browser.launch()

        Raises:
            RuntimeError: If Playwright fails to start or browser fails to launch
        """
        self.browser_type = browser_type
        self.headless = headless
        self.browser_kwargs = browser_kwargs

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._console_messages: list[dict[str, Any]] = []

        # Initialize will be called later when we're in an async context
        self._initialized = False

    async def _initialize(self) -> None:
        """Initialize Playwright, browser, context, and page."""
        try:
            self._playwright = await async_playwright().start()

            # Get the browser launcher based on type
            if self.browser_type == "chromium":
                launcher = self._playwright.chromium
            elif self.browser_type == "firefox":
                launcher = self._playwright.firefox
            elif self.browser_type == "webkit":
                launcher = self._playwright.webkit
            else:
                raise ValueError(f"Unsupported browser type: {self.browser_type}")

            # Launch browser
            self._browser = await launcher.launch(headless=self.headless, **self.browser_kwargs)

            # Create context and page
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()

            # Set up console message collection
            self._page.on("console", self._handle_console_message)
            
            self._initialized = True

        except Exception as e:
            await self.close()
            raise RuntimeError(f"Failed to initialize Playwright: {e}") from e

    def _handle_console_message(self, msg: Any) -> None:
        """Handle console messages from the page."""
        self._console_messages.append(
            {
                "type": msg.type,
                "text": msg.text,
                "args": [str(arg) for arg in msg.args],
                "location": {
                    "url": msg.location.get("url") if msg.location else None,
                    "line": msg.location.get("lineNumber") if msg.location else None,
                    "column": msg.location.get("columnNumber") if msg.location else None,
                },
            }
        )

    async def navigate(
        self,
        url: str,
        wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] | None = "networkidle",
    ) -> dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation complete

        Returns:
            Dictionary with navigation result information

        Raises:
            RuntimeError: If navigation fails or Playwright not initialized
        """
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
        """
        Capture accessibility snapshot of the current page.

        Returns:
            Dictionary containing the accessibility tree snapshot

        Raises:
            RuntimeError: If snapshot fails or Playwright not initialized
        """
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

    async def get_console_messages(self, clear: bool = False) -> list[dict[str, Any]]:
        """
        Get console messages from the current page.

        Args:
            clear: Whether to clear the message buffer after retrieving

        Returns:
            List of console message dictionaries
        """
        messages = self._console_messages.copy()

        if clear:
            self._console_messages.clear()

        return messages

    async def close(self) -> None:
        """Close the Playwright instance and clean up resources."""
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
            # Ignore errors during cleanup
            pass

    @property
    def is_initialized(self) -> bool:
        """Check if Playwright is properly initialized."""
        return self._initialized

    @property
    def current_url(self) -> str | None:
        """Get the current page URL."""
        return self._page.url if self._page else None

    async def initialize(self) -> None:
        """Public method to initialize Playwright"""
        if not self._initialized:
            await self._initialize()

    async def __aenter__(self):
        """Async context manager entry."""
        if not self._initialized:
            await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
