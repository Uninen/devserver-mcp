from unittest.mock import AsyncMock, MagicMock

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import DevServerTUI, LogsWidget, ServerBox


@pytest.fixture
def sample_config():
    return Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
            "backend": ServerConfig(command="python -m backend", working_dir="./backend", port=8000),
        }
    )


@pytest.fixture
def manager(sample_config):
    return DevServerManager(sample_config)


@pytest.fixture
def config_with_log_prefix_options():
    return Config(
        servers={
            "log_prefix_server": ServerConfig(
                command="echo 'prefixed'",
                working_dir=".",
                port=9001,
                prefix_logs=True,
            ),
            "no_log_prefix_server": ServerConfig(
                command="echo 'not prefixed'",
                working_dir=".",
                port=9002,
                prefix_logs=False,
            ),
        }
    )


@pytest.fixture
def manager_for_log_prefix_tests(config_with_log_prefix_options):
    return DevServerManager(config_with_log_prefix_options)


async def test_server_box_click_start_stopped_server(manager):
    server = {"name": "frontend", "status": "stopped", "external_running": False, "error": None}
    box = ServerBox(server, manager)

    manager.start_server = AsyncMock()
    mock_event = MagicMock()

    await box.on_click(mock_event)

    manager.start_server.assert_called_once_with("frontend")


async def test_server_box_click_stop_running_managed_server(manager):
    server = {"name": "backend", "status": "running", "external_running": False, "error": None}
    box = ServerBox(server, manager)

    manager.stop_server = AsyncMock()
    mock_event = MagicMock()

    await box.on_click(mock_event)

    manager.stop_server.assert_called_once_with("backend")


async def test_server_box_click_external_server_no_action(manager):
    server = {"name": "external", "status": "running", "external_running": True, "error": None}
    box = ServerBox(server, manager)

    manager.start_server = AsyncMock()
    manager.stop_server = AsyncMock()
    mock_event = MagicMock()

    await box.on_click(mock_event)

    manager.start_server.assert_not_called()
    manager.stop_server.assert_not_called()


async def test_server_box_click_error_server_no_action(manager):
    server = {"name": "error_server", "status": "error", "external_running": False, "error": "Connection failed"}
    box = ServerBox(server, manager)

    manager.start_server = AsyncMock()
    manager.stop_server = AsyncMock()
    mock_event = MagicMock()

    await box.on_click(mock_event)

    manager.start_server.assert_not_called()
    manager.stop_server.assert_not_called()


async def test_logs_widget_prefix_enabled(manager_for_log_prefix_tests):
    widget = LogsWidget(manager_for_log_prefix_tests)
    mock_rich_log = MagicMock()
    widget.query_one = MagicMock(return_value=mock_rich_log)

    server_name = "log_prefix_server"
    timestamp = "10:00:00"
    message = "Log message with prefix"

    await widget.add_log_line(server_name, timestamp, message)

    mock_rich_log.write.assert_called_once()
    formatted_message = mock_rich_log.write.call_args[0][0]

    assert f"[dim]{timestamp}[/dim]" in formatted_message
    assert (
        f"[{manager_for_log_prefix_tests.processes[server_name.lower()].color}]{server_name}[/{manager_for_log_prefix_tests.processes[server_name.lower()].color}]"
        in formatted_message
    )
    assert f" | {message}" in formatted_message
    assert message == formatted_message.split(" | ")[-1]


async def test_logs_widget_prefix_disabled(manager_for_log_prefix_tests):
    widget = LogsWidget(manager_for_log_prefix_tests)
    mock_rich_log = MagicMock()
    widget.query_one = MagicMock(return_value=mock_rich_log)

    sent_server_arg = ""
    sent_timestamp_arg = ""
    message = "Log message without prefix"

    await widget.add_log_line(sent_server_arg, sent_timestamp_arg, message)

    mock_rich_log.write.assert_called_once_with(message)


async def test_dev_server_start(manager):
    """Critical test - ensures app can start without crashing"""
    mcp_url = "http://localhost:3001/mcp/"
    app = DevServerTUI(manager, mcp_url)
    try:
        async with app.run_test() as _pilot:
            pass
    except Exception as e:
        pytest.fail(f"App failed to start during initialization: {e}")


async def test_dev_server_app_quit_action(manager):
    app = DevServerTUI(manager, "http://localhost:3001/mcp/")

    app.exit = MagicMock()
    manager.shutdown_all = AsyncMock()

    await app.action_quit()

    app.exit.assert_called_once_with(0)
    manager.shutdown_all.assert_called_once()
