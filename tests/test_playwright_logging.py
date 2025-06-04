import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.manager import DevServerManager
from devserver_mcp.ui import LogsWidget
from devserver_mcp.utils import get_tool_emoji


@pytest.fixture
def config_with_playwright():
    return {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }


@pytest.mark.asyncio
async def test_playwright_logs_should_have_proper_formatting():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        logs_widget = LogsWidget(manager)
        mock_rich_log = MagicMock()
        logs_widget.query_one = MagicMock(return_value=mock_rich_log)

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.is_initialized = True

            await manager.autostart_configured_servers()

            mock_rich_log.write.assert_called()

            logged_calls = mock_rich_log.write.call_args_list
            logged_messages = [call[0][0] for call in logged_calls]

            playwright_messages = [msg for msg in logged_messages if "Playwright" in msg or "Browser" in msg]

            assert len(playwright_messages) > 0, (
                "No Playwright messages found in logs - Playwright operations are not being logged"
            )

            properly_formatted_messages = [
                msg for msg in playwright_messages if get_tool_emoji() in msg and "Playwright" in msg and "|" in msg
            ]

            assert len(properly_formatted_messages) > 0, (
                f"Playwright messages lack proper formatting. Found messages: \
                    {playwright_messages}. Expected format: '[timestamp] \
                        [🔧  Playwright] | message'"
            )


@pytest.mark.asyncio
async def test_playwright_autostart_message_formatting():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        manager.add_log_callback(capture_log)

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.is_initialized = True

            await manager.autostart_configured_servers()

            playwright_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "Playwright" in server or "Browser" in message or "playwright" in message.lower()
            ]

            assert len(playwright_logs) > 0, f"No Playwright logs captured. All logs: {captured_logs}"

            expected_server_name = f"{get_tool_emoji()} Playwright"
            playwright_server_logs = [
                (server, timestamp, message)
                for server, timestamp, message in playwright_logs
                if server == expected_server_name
            ]

            assert len(playwright_server_logs) > 0, (
                f"No logs with proper server name '{expected_server_name}'. Playwright logs: {playwright_logs}"
            )


@pytest.mark.asyncio
async def test_playwright_operation_logs_have_timestamps():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        manager.add_log_callback(capture_log)

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.navigate = AsyncMock(return_value={"url": "http://example.com", "title": "Example"})
            mock_playwright.is_initialized = True

            await manager.autostart_configured_servers()

            await manager.playwright_navigate("http://example.com")

            navigation_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "navigate" in message.lower() or "example.com" in message.lower() or "Browser" in message
            ]

            assert len(navigation_logs) > 0, f"No navigation logs found. All logs: {captured_logs}"

            timestamped_logs = [
                (server, timestamp, message)
                for server, timestamp, message in navigation_logs
                if timestamp and ":" in timestamp and len(timestamp.split(":")) >= 2
            ]

            assert len(timestamped_logs) > 0, (
                f"No properly timestamped navigation logs. Navigation logs: {navigation_logs}"
            )
