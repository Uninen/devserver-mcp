import tempfile
from unittest.mock import patch, MagicMock
import pytest
import yaml
import sys

from devserver_mcp.config import load_config
from devserver_mcp.manager import DevServerManager


def test_playwright_import_error_when_module_not_installed():
    """Test that Playwright initialization handles missing module gracefully"""
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
        
        original_import = __builtins__['__import__']
        def mock_import(name, *args, **kwargs):
            if name == 'devserver_mcp.playwright':
                raise ModuleNotFoundError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)
            
        with patch('builtins.__import__', side_effect=mock_import):
            manager = DevServerManager(config)
            
            assert manager.playwright_enabled is True
            assert manager._playwright_operator is None
            assert manager.playwright_running is False
            assert manager._playwright_init_error is not None


@pytest.mark.asyncio
async def test_playwright_commands_error_when_module_not_installed():
    """Test that Playwright commands return proper error when module is not installed"""
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
        
        original_import = __builtins__['__import__']
        def mock_import(name, *args, **kwargs):
            if name == 'devserver_mcp.playwright':
                raise ModuleNotFoundError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)
            
        with patch('builtins.__import__', side_effect=mock_import):
            manager = DevServerManager(config)
            
            result = await manager.playwright_navigate("http://example.com")
            assert result["status"] == "error"
            assert "Playwright not available" in result["message"]
            
            result = await manager.playwright_snapshot()
            assert result["status"] == "error"
            assert "Playwright not available" in result["message"]
            
            result = await manager.playwright_console_messages()
            assert result["status"] == "error"
            assert "Playwright not available" in result["message"]


@pytest.mark.asyncio
async def test_ui_shows_error_state_when_playwright_module_missing():
    """Test that UI shows error state when Playwright module is missing"""
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
        
        log_messages = []
        async def track_notify_log(box, time, message):
            log_messages.append((box, time, message))
        
        original_import = __builtins__['__import__']
        def mock_import(name, *args, **kwargs):
            if name == 'devserver_mcp.playwright':
                raise ModuleNotFoundError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)
            
        with patch('builtins.__import__', side_effect=mock_import):
            manager = DevServerManager(config)
            manager._notify_log = track_notify_log
            
            await manager.autostart_configured_servers()
            
            assert manager._playwright_operator is None
            assert manager.playwright_running is False
            
            error_logs = [msg for box, time, msg in log_messages if "Playwright" in box and "Failed" in msg]
            assert len(error_logs) > 0, "UI did not receive error notification for missing Playwright module"