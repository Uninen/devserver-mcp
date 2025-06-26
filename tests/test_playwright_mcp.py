import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.utils import get_tool_emoji


def test_playwright_disabled_by_default():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        assert not manager.playwright_enabled
        assert not manager.playwright_running


def test_playwright_enabled_with_experimental_config():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)

            assert manager.playwright_enabled
            mock_playwright.assert_called_once_with(headless=True)


def test_playwright_disabled_when_experimental_false():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": False},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        assert not manager.playwright_enabled
        assert not manager.playwright_running


@pytest.mark.asyncio
async def test_mcp_commands_added_when_playwright_enabled():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            mcp = create_mcp_server(manager)

            tools = await mcp.get_tools()
            tool_names = list(tools.keys())
            assert "browser_navigate" in tool_names
            assert "browser_snapshot" in tool_names
            assert "browser_console_messages" in tool_names
            assert "browser_click" in tool_names
            assert "browser_type" in tool_names
            assert "browser_resize" in tool_names
            assert "browser_screenshot" in tool_names


@pytest.mark.asyncio
async def test_mcp_commands_not_added_when_playwright_disabled():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)
        mcp = create_mcp_server(manager)

        tools = await mcp.get_tools()
        tool_names = list(tools.keys())
        assert "browser_navigate" not in tool_names
        assert "browser_snapshot" not in tool_names
        assert "browser_console_messages" not in tool_names


@pytest.mark.asyncio
async def test_playwright_navigate_error_handling():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.navigate = AsyncMock(side_effect=Exception("Navigation failed"))
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)

            result = await manager.playwright_navigate("http://example.com")
            assert result["status"] == "error"
            assert "Navigation failed" in result["message"]


@pytest.mark.asyncio
async def test_playwright_navigate_when_disabled():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        result = await manager.playwright_navigate("http://example.com")
        assert result["status"] == "error"
        assert result["message"] == "Playwright not available"


@pytest.mark.asyncio
async def test_playwright_shutdown():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.close = AsyncMock()
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            await manager.shutdown_all()

            mock_instance.close.assert_called_once()


@pytest.mark.asyncio
async def test_playwright_autostart_integration():
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

        from devserver_mcp import DevServerMCP

        try:
            mcp_server = DevServerMCP(config=config, port=3002, _skip_port_check=True)

            assert mcp_server.manager.playwright_enabled

            await mcp_server.manager.autostart_configured_servers()

            mcp = mcp_server.mcp
            tools = await mcp.get_tools()
            tool_names = list(tools.keys())

            assert "browser_navigate" in tool_names
            assert "browser_snapshot" in tool_names
            assert "browser_console_messages" in tool_names
            assert "browser_click" in tool_names
            assert "browser_type" in tool_names
            assert "browser_resize" in tool_names
            assert "browser_screenshot" in tool_names

            await mcp_server.manager.shutdown_all()

        except Exception as e:
            pytest.fail(f"Real application startup failed with Playwright enabled: {e}")


@pytest.mark.asyncio
async def test_playwright_mcp_commands_real_execution():
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

        result = await manager.playwright_navigate("https://example.com")

        assert "status" in result
        assert result["status"] in ["error", "success"]

        result = await manager.playwright_snapshot()
        assert "status" in result
        assert result["status"] in ["error", "success"]

        result = await manager.playwright_console_messages()
        assert "status" in result
        assert result["status"] in ["error", "success"]

        await manager.shutdown_all()


@pytest.mark.asyncio
async def test_playwright_ui_status_synchronization():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.is_initialized = False  # Initially not initialized
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)

            assert manager.playwright_enabled
            assert not manager.playwright_running

            async def mock_initialize():
                mock_instance.is_initialized = True

            mock_instance.initialize = AsyncMock(side_effect=mock_initialize)

            status_change_called = []
            original_notify = manager._notify_status_change

            def track_status_change():
                status_change_called.append(True)
                original_notify()

            manager._notify_status_change = track_status_change

            await manager.autostart_configured_servers()

            assert mock_instance.initialize.called
            assert manager._playwright_operator.is_initialized  # type: ignore
            assert manager.playwright_running

            assert len(status_change_called) > 0, (
                "UI status change not triggered after Playwright startup - "
                "TUI will show STOPPED despite successful start"
            )

            await manager.shutdown_all()


@pytest.mark.asyncio
async def test_playwright_resize_error_handling():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.resize = AsyncMock(side_effect=Exception("Viewport resize failed"))
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)

            result = await manager.playwright_resize(1920, 1080)

            assert result["status"] == "error"
            assert "Viewport resize failed" in result["message"]


@pytest.mark.asyncio
async def test_playwright_resize_when_disabled():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        result = await manager.playwright_resize(1920, 1080)

        assert result["status"] == "error"
        assert result["message"] == "Playwright not available"


@pytest.mark.asyncio
async def test_playwright_resize_logging():
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

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.resize = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Resized viewport to 1280x720",
                    "width": 1280,
                    "height": 720,
                    "url": "https://example.com",
                }
            )
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            manager.add_log_callback(capture_log)

            await manager.playwright_resize(1280, 720)

            resize_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "resize" in message.lower() or "1280x720" in message
            ]

            assert len(resize_logs) > 0, f"No resize logs captured. All logs: {captured_logs}"

            resize_log = resize_logs[0]
            assert f"{get_tool_emoji()} Playwright" in resize_log[0]
            assert "Resized viewport to 1280x720" in resize_log[2]


@pytest.mark.asyncio
async def test_playwright_screenshot_error_handling():
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

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)

            result = await manager.playwright_screenshot()

            assert result["status"] == "error"
            assert "Screenshot failed" in result["message"]


@pytest.mark.asyncio
async def test_playwright_screenshot_when_disabled():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        manager = DevServerManager(config)

        result = await manager.playwright_screenshot()

        assert result["status"] == "error"
        assert result["message"] == "Playwright not available"


@pytest.mark.asyncio
async def test_playwright_screenshot_logging():
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

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.screenshot = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Screenshot saved to screenshots/screenshot_20241226_120000.png",
                    "filename": "screenshot_20241226_120000.png",
                    "path": "screenshots/screenshot_20241226_120000.png",
                    "url": "https://example.com",
                    "full_page": False,
                }
            )
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            manager.add_log_callback(capture_log)

            await manager.playwright_screenshot()

            screenshot_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "screenshot" in message.lower()
            ]

            assert len(screenshot_logs) > 0, f"No screenshot logs captured. All logs: {captured_logs}"

            screenshot_log = screenshot_logs[0]
            assert f"{get_tool_emoji()} Playwright" in screenshot_log[0]
            assert "Screenshot saved to" in screenshot_log[2]


@pytest.mark.asyncio
async def test_playwright_screenshot_with_name():
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

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.screenshot = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Screenshot saved to screenshots/my_test_screenshot.png",
                    "filename": "my_test_screenshot.png",
                    "path": "screenshots/my_test_screenshot.png",
                    "url": "https://example.com",
                    "full_page": False,
                }
            )
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            manager.add_log_callback(capture_log)

            await manager.playwright_screenshot(name="my_test_screenshot")

            screenshot_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "screenshot" in message.lower()
            ]

            assert len(screenshot_logs) > 0
            assert "as 'my_test_screenshot'" in screenshot_logs[0][2]


@pytest.mark.asyncio
async def test_playwright_screenshot_full_page():
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

        captured_logs = []

        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))

        with patch("devserver_mcp.playwright.PlaywrightOperator") as mock_playwright:
            mock_instance = MagicMock()
            mock_instance.screenshot = AsyncMock(
                return_value={
                    "status": "success",
                    "message": "Screenshot saved to screenshots/screenshot_20241226_120000.png",
                    "filename": "screenshot_20241226_120000.png",
                    "path": "screenshots/screenshot_20241226_120000.png",
                    "url": "https://example.com",
                    "full_page": True,
                }
            )
            mock_playwright.return_value = mock_instance

            manager = DevServerManager(config)
            manager.add_log_callback(capture_log)

            await manager.playwright_screenshot(full_page=True)

            # Verify the method was called with correct parameters
            mock_instance.screenshot.assert_called_once_with(True, None)

            screenshot_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "screenshot" in message.lower()
            ]

            assert len(screenshot_logs) > 0
            assert "(full page)" in screenshot_logs[0][2]
