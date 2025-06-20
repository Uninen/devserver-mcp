import io
from unittest.mock import patch

import pytest
from fastmcp import Client

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
                port=8001,
            )
        }
    )


@pytest.fixture
def manager(test_config):
    return DevServerManager(test_config)


@pytest.mark.asyncio
async def test_mcp_logging_captured_via_callback(manager):
    logged_messages = []

    async def capture_log(server_name, timestamp, message):
        logged_messages.append({"server": server_name, "timestamp": timestamp, "message": message})

    manager.add_log_callback(capture_log)

    mcp_server = create_mcp_server(manager)

    async with Client(mcp_server) as client:
        await client.call_tool("get_server_status", {"name": "test-server"})

    mcp_logs = [log for log in logged_messages if log["server"] == "MCP Server"]
    assert len(mcp_logs) > 0, "MCP operations should generate log messages"


@pytest.mark.asyncio
async def test_mcp_logging_isolation_from_terminal(manager):
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()

    with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
        mcp_server = create_mcp_server(manager)

        async with Client(mcp_server) as client:
            await client.call_tool("get_server_status", {"name": "test-server"})
            await client.call_tool("start_server", {"name": "test-server"})

    stdout_content = stdout_capture.getvalue()
    stderr_content = stderr_capture.getvalue()

    assert stdout_content == "", f"MCP operations leaked to stdout: {repr(stdout_content)}"
    assert stderr_content == "", f"MCP operations leaked to stderr: {repr(stderr_content)}"
