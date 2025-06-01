from unittest.mock import AsyncMock, patch

import pytest

from devserver_mcp import DevServerMCP
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def config_with_playwright():
    """Config with playwright enabled and autostart frontend."""
    return Config(
        servers={
            "frontend": ServerConfig(
                command="echo test",
                working_dir=".",
                port=5173,
                autostart=True,
            )
        },
        experimental_playwright=True,
    )


@pytest.mark.asyncio
async def test_playwright_manager_launches_browser_on_startup(config_with_playwright):
    """Test that PlaywrightManager launches browser when the app starts with TUI."""
    with (
        patch("devserver_mcp.DevServerTUI") as mock_tui_cls,
        patch("devserver_mcp.manager.PlaywrightManager") as mock_playwright_cls,
        patch("fastmcp.FastMCP.run_async") as mock_mcp_run,
    ):
        # Setup mocks
        mock_playwright = AsyncMock()
        mock_playwright.launch_browser = AsyncMock()
        mock_playwright_cls.return_value = mock_playwright

        mock_tui = AsyncMock()
        mock_tui.run_async = AsyncMock()
        mock_tui_cls.return_value = mock_tui

        mock_mcp_run.return_value = None

        # Create DevServerMCP instance
        server = DevServerMCP(config=config_with_playwright, port=8081)

        # Verify PlaywrightManager was created
        assert server.manager.playwright_manager is not None
        mock_playwright_cls.assert_called_once()

        # This should fail currently because the app doesn't properly start
        # and launch the browser
        await server.run()

        # Verify that autostart_configured_servers was called, which should launch the browser
        # Currently this will fail because the TUI's on_mount is mocked and never calls autostart
        mock_playwright.launch_browser.assert_called_once()


@pytest.mark.asyncio
async def test_headless_mode_starts_mcp_and_autostarts_servers():
    """Test that headless mode starts MCP server and autostarts configured servers including Playwright."""
    config = Config(
        servers={
            "backend": ServerConfig(
                command="echo test",
                working_dir=".",
                port=8000,
                autostart=True,
            )
        },
        experimental_playwright=True,
    )

    with (
        patch("devserver_mcp.manager.PlaywrightManager") as mock_playwright_cls,
        patch("sys.stdout.isatty", return_value=False),  # Force headless mode
        patch("sys.stderr.isatty", return_value=False),
        patch("fastmcp.FastMCP.run_async") as mock_mcp_run,
    ):
        mock_playwright = AsyncMock()
        mock_playwright.launch_browser = AsyncMock()
        mock_playwright_cls.return_value = mock_playwright

        mock_mcp_run.return_value = None

        server = DevServerMCP(config=config, port=8082)

        # In headless mode, this should start MCP server and autostart servers
        await server.run()

        # This should now pass since our fix makes headless mode call autostart_configured_servers
        mock_playwright.launch_browser.assert_called_once()
