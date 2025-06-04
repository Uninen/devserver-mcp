import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server


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
