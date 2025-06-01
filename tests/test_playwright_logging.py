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
    """Test that Playwright operations log with proper timestamp and tool emoji formatting.
    
    This test demonstrates that Playwright logs are currently not formatted correctly.
    They should appear as '[timestamp] [🔧 Playwright] | message' but instead appear as raw messages.
    """
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
        
        # Create LogsWidget to capture log messages
        logs_widget = LogsWidget(manager)
        mock_rich_log = MagicMock()
        logs_widget.query_one = MagicMock(return_value=mock_rich_log)

        # Mock the Playwright operator to control its behavior
        with patch('devserver_mcp.playwright.PlaywrightOperator') as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.is_initialized = True
            
            # This should trigger Playwright initialization and logging
            await manager.autostart_configured_servers()
            
            # Check if any logs were written to the logs widget
            # The test should FAIL because Playwright messages are not being logged properly
            mock_rich_log.write.assert_called()
            
            # Get all the logged messages
            logged_calls = mock_rich_log.write.call_args_list
            logged_messages = [call[0][0] for call in logged_calls]
            
            # Look for Playwright-related messages
            playwright_messages = [msg for msg in logged_messages if "Playwright" in msg or "Browser" in msg]
            
            # This assertion should FAIL - no properly formatted Playwright messages exist
            assert len(playwright_messages) > 0, "No Playwright messages found in logs - Playwright operations are not being logged"
            
            # Check if any Playwright message has proper formatting with emoji and timestamp
            properly_formatted_messages = [
                msg for msg in playwright_messages 
                if get_tool_emoji() in msg and "Playwright" in msg and "|" in msg
            ]
            
            # This assertion should FAIL - Playwright messages lack proper formatting
            assert len(properly_formatted_messages) > 0, f"Playwright messages lack proper formatting. Found messages: {playwright_messages}. Expected format: '[timestamp] [🔧 Playwright] | message'"


@pytest.mark.asyncio 
async def test_playwright_autostart_message_formatting():
    """Test that Playwright autostart success message is formatted correctly.
    
    This test specifically checks that when Playwright starts successfully during autostart,
    the success message appears in the TUI logs with proper formatting.
    """
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
        
        # Track log messages
        captured_logs = []
        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))
        
        manager.add_log_callback(capture_log)

        # Mock successful Playwright initialization
        with patch('devserver_mcp.playwright.PlaywrightOperator') as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.is_initialized = True
            
            # Trigger autostart which should log Playwright messages
            await manager.autostart_configured_servers()
            
            # Look for Playwright success messages in captured logs
            playwright_logs = [
                (server, timestamp, message) 
                for server, timestamp, message in captured_logs 
                if "Playwright" in server or "Browser" in message or "playwright" in message.lower()
            ]
            
            # This should FAIL - no Playwright logs are captured because they're not sent through the logging system
            assert len(playwright_logs) > 0, f"No Playwright logs captured. All logs: {captured_logs}"
            
            # Check that at least one log has the expected server name format
            expected_server_name = f"{get_tool_emoji()} Playwright"
            playwright_server_logs = [
                (server, timestamp, message)
                for server, timestamp, message in playwright_logs
                if server == expected_server_name
            ]
            
            # This should FAIL - Playwright logs don't use the correct server name format
            assert len(playwright_server_logs) > 0, f"No logs with proper server name '{expected_server_name}'. Playwright logs: {playwright_logs}"


@pytest.mark.asyncio
async def test_playwright_operation_logs_have_timestamps():
    """Test that Playwright operations (navigate, snapshot, etc.) produce timestamped logs.
    
    This test verifies that when Playwright operations are performed,
    they generate log messages with timestamps like other server operations.
    """
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
        
        # Track all log messages
        captured_logs = []
        async def capture_log(server: str, timestamp: str, message: str):
            captured_logs.append((server, timestamp, message))
        
        manager.add_log_callback(capture_log)

        # Mock Playwright operator
        with patch('devserver_mcp.playwright.PlaywrightOperator') as mock_playwright_class:
            mock_playwright = MagicMock()
            mock_playwright_class.return_value = mock_playwright
            mock_playwright.initialize = AsyncMock()
            mock_playwright.navigate = AsyncMock(return_value={"url": "http://example.com", "title": "Example"})
            mock_playwright.is_initialized = True
            
            # Initialize Playwright and perform operations
            await manager.autostart_configured_servers()
            
            # Perform a Playwright operation that should be logged
            await manager.playwright_navigate("http://example.com")
            
            # Look for any logs related to the navigation operation
            navigation_logs = [
                (server, timestamp, message)
                for server, timestamp, message in captured_logs
                if "navigate" in message.lower() or "example.com" in message.lower() or "Browser" in message
            ]
            
            # This should FAIL - Playwright operations don't generate logged messages
            assert len(navigation_logs) > 0, f"No navigation logs found. All logs: {captured_logs}"
            
            # Check that navigation logs have proper timestamp format (HH:MM:SS)
            timestamped_logs = [
                (server, timestamp, message)
                for server, timestamp, message in navigation_logs
                if timestamp and ":" in timestamp and len(timestamp.split(":")) >= 2
            ]
            
            # This should FAIL - Playwright operation logs lack proper timestamps
            assert len(timestamped_logs) > 0, f"No properly timestamped navigation logs. Navigation logs: {navigation_logs}"