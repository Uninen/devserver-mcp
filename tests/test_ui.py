from unittest.mock import MagicMock

import pytest

from devserver_mcp.manager import Config, DevServerManager, ServerConfig
from devserver_mcp.ui import DevServerApp, LogsWidget, ServerStatusWidget


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
    running_server = {"status": "running", "external_running": False, "uptime": 120, "error": None}
    assert widget._format_status(running_server) == "● Running"
    assert widget._format_uptime_or_error(running_server) == "120s"

    # Test external status
    external_server = {"status": "stopped", "external_running": True, "uptime": None, "error": None}
    assert widget._format_status(external_server) == "● External"
    assert widget._format_uptime_or_error(external_server) == "External process"

    # Test error status
    error_server = {"status": "error", "external_running": False, "uptime": None, "error": "Connection failed"}
    assert widget._format_status(error_server) == "● Error"
    assert widget._format_uptime_or_error(error_server) == "Connection failed"

    # Test stopped status
    stopped_server = {"status": "stopped", "external_running": False, "uptime": None, "error": None}
    assert widget._format_status(stopped_server) == "● Stopped"
    assert widget._format_uptime_or_error(stopped_server) == "-"


async def test_server_status_widget_long_error_truncation(manager):
    """Test that long error messages are truncated"""
    widget = ServerStatusWidget(manager)

    long_error_server = {
        "status": "error",
        "external_running": False,
        "uptime": None,
        "error": "This is a very long error message that should be truncated",
    }

    formatted = widget._format_uptime_or_error(long_error_server)
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
    app = DevServerApp(manager, mcp_url)

    assert app.manager is manager
    assert app.mcp_url == mcp_url

    # Title is set on mount, so we need to check the initial state and post-mount
    assert app.title == "DevServerApp"  # Default title before mount

    # Simulate mounting to set the title
    app.on_mount()
    assert app.title == "DevServer MCP"
    assert app.sub_title == "Development Server Manager"


async def test_dev_server_app_quit_action(manager):
    """Test the quit action"""
    app = DevServerApp(manager, "http://localhost:3001/mcp/")

    # Mock the exit method
    app.exit = MagicMock()

    # Test quit action
    app.action_quit()

    app.exit.assert_called_once_with(0)


async def test_dev_server_app_compose_structure(manager):
    """Test the app composition structure"""
    app = DevServerApp(manager, "http://localhost:3001/mcp/")

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
