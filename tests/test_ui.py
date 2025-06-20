from unittest.mock import patch

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import DevServerTUI, LogsWidget, ServerBox, ToolBox


@pytest.fixture
def manager(multi_server_config, temp_state_dir):
    return DevServerManager(multi_server_config)


@pytest.fixture
def running_manager(running_multi_server_config, temp_state_dir):
    return DevServerManager(running_multi_server_config)


async def test_server_box_click_starts_stopped_server(running_manager):
    server = {"name": "api", "status": "stopped", "external_running": False, "error": None}
    box = ServerBox(server, running_manager)

    event = type("MockEvent", (), {"stop": lambda: None})()
    await box.on_click(event)

    status = running_manager.get_server_status("api")
    assert status["status"] == "running"

    await running_manager.stop_server("api")


async def test_server_box_click_stops_running_server(running_manager):
    await running_manager.start_server("web")

    server = {"name": "web", "status": "running", "external_running": False, "error": None}
    box = ServerBox(server, running_manager)

    event = type("MockEvent", (), {"stop": lambda: None})()
    await box.on_click(event)

    status = running_manager.get_server_status("web")
    assert status["status"] == "stopped"


async def test_server_box_no_action_on_external_server(manager):
    server = {"name": "external", "status": "running", "external_running": True, "error": None}
    box = ServerBox(server, manager)

    event = type("MockEvent", (), {"stop": lambda: None})()
    await box.on_click(event)

    # No assertion needed - just verify no exception raised


async def test_logs_widget_formatting():
    config = Config(
        servers={
            "prefixed": ServerConfig(command="echo test", working_dir=".", port=9001, prefix_logs=True),
            "unprefixed": ServerConfig(command="echo test", working_dir=".", port=9002, prefix_logs=False),
        }
    )
    manager = DevServerManager(config)
    widget = LogsWidget(manager)

    # Test that widget is created without errors
    assert widget is not None


async def test_dev_server_tui_initialization(manager):
    mcp_url = "http://localhost:3001/mcp/"
    app = DevServerTUI(manager, mcp_url)

    assert app.manager == manager
    assert app.mcp_url == mcp_url
    assert app.transport == "streamable-http"

    app_sse = DevServerTUI(manager, mcp_url, transport="sse")
    assert app_sse.transport == "sse"


async def test_dev_server_tui_runs_without_crash(manager):
    app = DevServerTUI(manager, "http://localhost:3001/mcp/")

    try:
        async with app.run_test():
            pass
    except Exception as e:
        pytest.fail(f"App failed to start: {e}")


async def test_dev_server_tui_quit_action(manager):
    app = DevServerTUI(manager, "http://localhost:3001/mcp/")

    await manager.start_server("api")
    await manager.start_server("web")

    with patch.object(app, "exit") as mock_exit:
        await app.action_quit()
        mock_exit.assert_called_once_with(0)

    assert manager.get_server_status("api")["status"] == "stopped"
    assert manager.get_server_status("web")["status"] == "stopped"


def test_tool_box_status_formatting():
    manager = type("MockManager", (), {})()

    tool_box_running = ToolBox("Playwright", "running", manager)
    assert tool_box_running._format_status_indicator() == "[#00ff80]●[/#00ff80]"

    tool_box_stopped = ToolBox("Playwright", "stopped", manager)
    assert tool_box_stopped._format_status_indicator() == "[#8000ff]●[/#8000ff]"

    tool_box_error = ToolBox("Playwright", "error", manager)
    assert tool_box_error._format_status_indicator() == "[#ff0040]●[/#ff0040]"


def test_tool_box_emoji():
    manager = type("MockManager", (), {})()

    tool_box = ToolBox("Playwright", "running", manager)
    assert tool_box._get_tool_emoji() == "🔧"


async def test_dev_server_tui_bottom_bar_displays_transport(manager):
    # Test HTTP transport
    app_http = DevServerTUI(manager, "http://localhost:3001/mcp/", transport="streamable-http")
    async with app_http.run_test():
        bottom_bar = app_http.query_one("#bottom-bar")
        assert bottom_bar is not None
        bar_text = str(bottom_bar.renderable)
        assert "MCP (HTTP): http://localhost:3001/mcp/" in bar_text

    # Test SSE transport
    app_sse = DevServerTUI(manager, "http://localhost:3001/sse/", transport="sse")
    async with app_sse.run_test():
        bottom_bar = app_sse.query_one("#bottom-bar")
        assert bottom_bar is not None
        bar_text = str(bottom_bar.renderable)
        assert "MCP (SSE): http://localhost:3001/sse/" in bar_text
