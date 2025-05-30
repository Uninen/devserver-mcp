from unittest.mock import MagicMock

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import DevServerTUI, LogsWidget, ServerStatusWidget


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
            "backend": ServerConfig(command="python -m backend", working_dir="./backend", port=8000),
        }
    )


@pytest.fixture
def manager(sample_config):
    """Create a manager instance for testing"""
    return DevServerManager(sample_config)


# ServerStatusWidget tests


async def test_server_status_widget_initialization(manager):
    """Test that the widget initializes correctly"""
    widget = ServerStatusWidget(manager)

    assert widget.manager is manager
    # Verify that the widget registered itself for status callbacks
    assert widget.refresh_table in manager._status_callbacks


async def test_server_status_widget_formatting(manager):
    """Test status text formatting"""
    widget = ServerStatusWidget(manager)

    # Test running status
    running_server = {"status": "running", "external_running": False, "error": None}
    assert widget._format_status(running_server) == "● Running"
    assert widget._format_error(running_server) == "Running"

    # Test external status
    external_server = {"status": "stopped", "external_running": True, "error": None}
    assert widget._format_status(external_server) == "● External"
    assert widget._format_error(external_server) == "External process"

    # Test error status
    error_server = {"status": "error", "external_running": False, "error": "Connection failed"}
    assert widget._format_status(error_server) == "● Error"
    assert widget._format_error(error_server) == "Connection failed"

    # Test stopped status
    stopped_server = {"status": "stopped", "external_running": False, "error": None}
    assert widget._format_status(stopped_server) == "● Stopped"
    assert widget._format_error(stopped_server) == "-"


async def test_server_status_widget_long_error_truncation(manager):
    """Test that long error messages are truncated"""
    widget = ServerStatusWidget(manager)

    long_error_server = {
        "status": "error",
        "external_running": False,
        "error": "This is a very long error message that should be truncated",
    }

    formatted = widget._format_error(long_error_server)
    assert len(formatted) <= 33  # 30 chars + "..."
    assert formatted.endswith("...")


# LogsWidget tests


async def test_logs_widget_initialization(manager):
    """Test that the logs widget initializes correctly"""
    widget = LogsWidget(manager)

    assert widget.manager is manager
    # Verify that the widget registered itself for log callbacks
    assert widget.add_log_line in manager._log_callbacks


async def test_logs_widget_line_formatting(manager):
    """Test log line formatting with colors"""
    widget = LogsWidget(manager)

    # Mock the RichLog widget
    mock_rich_log = MagicMock()
    widget.query_one = MagicMock(return_value=mock_rich_log)

    # Test log formatting
    await widget.add_log_line("frontend", "12:34:56", "Server started")

    # Verify the formatted message was written
    mock_rich_log.write.assert_called_once()
    formatted_message = mock_rich_log.write.call_args[0][0]

    assert "[dim]12:34:56[/dim]" in formatted_message
    assert "[cyan]frontend[/cyan]" in formatted_message  # frontend gets cyan color
    assert "Server started" in formatted_message


async def test_logs_widget_unknown_server_color(manager):
    """Test log formatting for unknown server"""
    widget = LogsWidget(manager)

    # Mock the RichLog widget
    mock_rich_log = MagicMock()
    widget.query_one = MagicMock(return_value=mock_rich_log)

    # Test with unknown server
    await widget.add_log_line("unknown", "12:34:56", "Some message")

    # Verify white color is used as fallback
    mock_rich_log.write.assert_called_once()
    formatted_message = mock_rich_log.write.call_args[0][0]

    assert "[white]unknown[/white]" in formatted_message


# DevServerApp tests


async def test_dev_server_app_initialization(manager):
    """Test that the app initializes correctly"""
    mcp_url = "http://localhost:3001/mcp/"
    app = DevServerTUI(manager, mcp_url)

    assert app.manager is manager
    assert app.mcp_url == mcp_url

    # Simulate mounting to set the title
    app.on_mount()
    assert app.title == "DevServer MCP"
    assert app.sub_title == "Development Server Manager"


async def test_dev_server_app_quit_action(manager):
    """Test the quit action"""
    app = DevServerTUI(manager, "http://localhost:3001/mcp/")

    # Mock the exit method
    app.exit = MagicMock()

    # Test quit action
    app.action_quit()

    app.exit.assert_called_once_with(0)


async def test_dev_server_app_compose_structure(manager):
    """Test the app composition structure"""
    app = DevServerTUI(manager, "http://localhost:3001/mcp/")

    # We can't easily test the full compose result without running the app,
    # but we can verify the app has the expected attributes
    assert hasattr(app, "compose")
    assert hasattr(app, "CSS")
    assert hasattr(app, "BINDINGS")

    # Check that CSS contains expected selectors
    assert "#logs" in app.CSS
    assert "#status" in app.CSS
    assert "RichLog" in app.CSS
    assert "DataTable" in app.CSS

    # Check bindings exist
    assert app.BINDINGS is not None
    assert len(app.BINDINGS) > 0


# Integration tests


async def test_widget_manager_interaction(manager):
    """Test that widgets interact correctly with manager"""
    status_widget = ServerStatusWidget(manager)
    logs_widget = LogsWidget(manager)

    # Verify both widgets are registered for callbacks
    assert len(manager._status_callbacks) == 1
    assert len(manager._log_callbacks) == 1

    # Test status callback
    status_widget.update_table = MagicMock()
    manager._notify_status_change()
    status_widget.update_table.assert_called_once()

    # Test log callback
    logs_widget.query_one = MagicMock(return_value=MagicMock())
    await manager._notify_log("test", "12:34:56", "test message")

    # Should not raise any exceptions


async def test_dev_server_start(manager):
    """Test that the app starts without errors"""
    mcp_url = "http://localhost:3001/mcp/"
    app = DevServerTUI(manager, mcp_url)
    try:
        # The CSS is parsed during the __init__ or on_mount of the App.
        # If there are parsing errors, Textual typically raises an error or logs warnings.
        # We'll try to compose the app which forces CSS processing.
        # This is a bit indirect, but Textual doesn't offer a direct CSS validation API.
        async with app.run_test() as _pilot:  # Changed pilot to _pilot to fix lint error
            pass  # If it runs without crashing, CSS is likely fine
    except Exception as e:
        pytest.fail(f"App failed to start during initialization: {e}")
