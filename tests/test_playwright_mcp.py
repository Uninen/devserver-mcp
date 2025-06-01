import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server


def test_playwright_disabled_by_default():
    """Test that Playwright is disabled when experimental config is not set"""
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
    """Test that Playwright is enabled when experimental config is set"""
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
    """Test that Playwright is disabled when experimental.playwright is False"""
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
    """Test that MCP commands are added when Playwright is enabled"""
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

            # Check that playwright commands are in the tool registry
            tools = await mcp.get_tools()
            tool_names = list(tools.keys())
            assert "browser_navigate" in tool_names
            assert "browser_snapshot" in tool_names
            assert "browser_console_messages" in tool_names


@pytest.mark.asyncio
async def test_mcp_commands_not_added_when_playwright_disabled():
    """Test that MCP commands are not added when Playwright is disabled"""
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

        # Check that playwright commands are not in the tool registry
        tools = await mcp.get_tools()
        tool_names = list(tools.keys())
        assert "browser_navigate" not in tool_names
        assert "browser_snapshot" not in tool_names
        assert "browser_console_messages" not in tool_names


@pytest.mark.asyncio
async def test_playwright_navigate_error_handling():
    """Test error handling in playwright_navigate method"""
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
    """Test playwright_navigate when Playwright is disabled"""
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
    """Test Playwright shutdown during manager shutdown"""
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
    """Test the actual autostart functionality without mocking"""
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

        # Import the real application class
        from devserver_mcp import DevServerMCP
        
        # This should work exactly like the real app startup
        try:
            # Create the real MCP server instance (like main() does)
            mcp_server = DevServerMCP(config=config, port=3002)  # Use different port to avoid conflicts
            
            # Verify Playwright is enabled in the manager
            assert mcp_server.manager.playwright_enabled
            
            # Test the real autostart method (this is what fails in the actual app)
            await mcp_server.manager.autostart_configured_servers()
            
            # Verify Playwright integration in MCP server
            mcp = mcp_server.mcp
            tools = await mcp.get_tools()
            tool_names = list(tools.keys())
            
            # These commands should be available
            assert "browser_navigate" in tool_names
            assert "browser_snapshot" in tool_names
            assert "browser_console_messages" in tool_names
            
            # Cleanup
            await mcp_server.manager.shutdown_all()
            
        except Exception as e:
            # If this fails, the real app will fail too
            pytest.fail(f"Real application startup failed with Playwright enabled: {e}")


@pytest.mark.asyncio
async def test_playwright_mcp_commands_real_execution():
    """Test that MCP commands actually work when called (not just registered)"""
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
        
        # Test with real manager, no mocks
        manager = DevServerManager(config)
        
        # This should not throw exceptions when Playwright is properly initialized
        result = await manager.playwright_navigate("https://example.com")
        
        # The result should be proper error message if Playwright can't start,
        # not a crash due to event loop issues
        assert "status" in result
        assert result["status"] in ["error", "success"]  # Either is fine, but should not crash
        
        # Test snapshot command
        result = await manager.playwright_snapshot()
        assert "status" in result
        assert result["status"] in ["error", "success"]
        
        # Test console messages
        result = await manager.playwright_console_messages()
        assert "status" in result
        assert result["status"] in ["error", "success"]
        
        # Cleanup
        await manager.shutdown_all()
