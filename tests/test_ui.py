from unittest.mock import AsyncMock, MagicMock

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import DevServerTUI, LogsWidget, ServerBox, ToolBox


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


async def test_tool_box_formatting_with_emoji():
    manager = MagicMock()

    tool_box = ToolBox("Playwright", "running", manager)
    result = tool_box._format_tool_with_status()

    assert "🔧" in result
    assert "[b]Playwright[/b]" in result
    assert "[#00ff80]●[/#00ff80]" in result

    tool_box_stopped = ToolBox("Playwright", "stopped", manager)
    result_stopped = tool_box_stopped._format_tool_with_status()

    assert "🔧" in result_stopped
    assert "[#8000ff]●[/#8000ff]" in result_stopped

    tool_box_error = ToolBox("Playwright", "error", manager)
    result_error = tool_box_error._format_tool_with_status()

    assert "🔧" in result_error
    assert "[#ff0040]●[/#ff0040]" in result_error


async def test_tool_box_emoji_mapping():
    manager = MagicMock()

    playwright_box = ToolBox("Playwright", "running", manager)
    assert playwright_box._get_tool_emoji() == "🔧"

    other_box = ToolBox("SomeTool", "running", manager)
    assert other_box._get_tool_emoji() == "🔧"


async def test_tool_box_status_indicators():
    manager = MagicMock()
    tool_box = ToolBox("Playwright", "running", manager)

    tool_box.status = "running"
    assert tool_box._format_status_indicator() == "[#00ff80]●[/#00ff80]"

    tool_box.status = "error"
    assert tool_box._format_status_indicator() == "[#ff0040]●[/#ff0040]"

    tool_box.status = "stopped"
    assert tool_box._format_status_indicator() == "[#8000ff]●[/#8000ff]"


async def test_tool_box_update_status():
    manager = MagicMock()
    tool_box = ToolBox("Playwright", "stopped", manager)

    mock_label = MagicMock()
    tool_box.query_one = MagicMock(return_value=mock_label)

    tool_box.update_status("running")

    assert tool_box.status == "running"

    mock_label.update.assert_called_once()
    updated_text = mock_label.update.call_args[0][0]
    assert "🔧" in updated_text
    assert "[#00ff80]●[/#00ff80]" in updated_text


async def test_tool_box_compose():
    manager = MagicMock()
    tool_box = ToolBox("Playwright", "running", manager)

    compose_result = list(tool_box.compose())

    assert len(compose_result) == 1
    label = compose_result[0]
    assert hasattr(label, "id")
    assert label.id == "tool-display"


async def test_tool_box_visual_distinction_from_server_box():
    manager = MagicMock()

    tool_box = ToolBox("Playwright", "running", manager)
    tool_format = tool_box._format_tool_with_status()

    server = {"name": "test-server", "status": "running", "external_running": False}
    server_box = ServerBox(server, manager)
    server_format = server_box._format_status(server)

    assert "🔧" in tool_format
    assert "🔧" not in server_format

    assert "[b]Playwright[/b]" in tool_format and "●" in tool_format

    assert "Running" in server_format
    assert "Running" not in tool_format
