import io
from unittest.mock import patch

import pytest

from devserver_mcp import create_mcp_server
from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import DevServerTUI


@pytest.fixture
def test_config():
    return Config(
        servers={
            "test-server": ServerConfig(
                command="echo 'test'",
                working_dir=".",
                port=8000,
            )
        }
    )


@pytest.fixture
def manager(test_config):
    return DevServerManager(test_config)


@pytest.mark.asyncio
async def test_mcp_server_startup_logged_to_tui(manager):
    mcp_url = "http://localhost:3001/mcp/"
    DevServerTUI(manager, mcp_url)

    create_mcp_server(manager)

    logged_messages = []

    async def capture_log(server_name, timestamp, message):
        logged_messages.append({"server": server_name, "timestamp": timestamp, "message": message})

    manager.add_log_callback(capture_log)

    await manager._notify_log(
        "MCP Server",
        "12:00:00",
        f"MCP Server started at {mcp_url} (streamable-http transport)",
    )

    mcp_startup_logs = [
        log for log in logged_messages if log["server"] == "MCP Server" and "started at" in log["message"]
    ]

    assert len(mcp_startup_logs) > 0, "MCP server startup should be logged to TUI"
    assert mcp_url in mcp_startup_logs[0]["message"]
    assert "streamable-http transport" in mcp_startup_logs[0]["message"]


@pytest.mark.asyncio
async def test_mcp_tool_calls_logged_to_tui(manager):
    logged_messages = []

    async def capture_log(server_name, timestamp, message):
        logged_messages.append({"server": server_name, "timestamp": timestamp, "message": message})

    manager.add_log_callback(capture_log)

    await manager._notify_log("MCP Server", "12:00:01", "Tool 'start_server' called with: {'name': 'test-server'}")

    tool_logs = [log for log in logged_messages if log["server"] == "MCP Server" and "Tool" in log["message"]]

    assert len(tool_logs) == 1
    assert "Tool 'start_server' called with: {'name': 'test-server'}" in tool_logs[0]["message"]


@pytest.mark.asyncio
async def test_mcp_logging_doesnt_leak_to_terminal(manager):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
        logged_messages = []

        async def capture_log(server_name, timestamp, message):
            logged_messages.append({"server": server_name, "timestamp": timestamp, "message": message})

        manager.add_log_callback(capture_log)

        await manager._notify_log(
            "MCP Server", "12:00:00", "MCP Server started at http://localhost:3001/mcp/ (streamable-http transport)"
        )

        await manager._notify_log("MCP Server", "12:00:01", "Tool 'start_server' called with: {'name': 'test-server'}")

        await manager._notify_log(
            "MCP Server", "12:00:02", "Tool 'get_server_status' called with: {'name': 'test-server'}"
        )

    assert len(logged_messages) == 3, f"Expected 3 logged messages, got {len(logged_messages)}"

    stdout_content = stdout_capture.getvalue()
    stderr_content = stderr_capture.getvalue()

    assert stdout_content == "", f"MCP logging leaked to stdout: {repr(stdout_content)}"
    assert stderr_content == "", f"MCP logging leaked to stderr: {repr(stderr_content)}"

    assert "MCP Server started at" in logged_messages[0]["message"]
    assert "Tool 'start_server' called with" in logged_messages[1]["message"]
    assert "Tool 'get_server_status' called with" in logged_messages[2]["message"]
