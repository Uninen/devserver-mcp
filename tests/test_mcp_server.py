import json

import pytest
from fastmcp import Client

from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def test_config():
    return Config(
        servers={
            "test-server": ServerConfig(
                command="echo 'test server'",
                working_dir=".",
                port=8000,
            )
        }
    )


@pytest.fixture
def manager(test_config):
    return DevServerManager(test_config)


@pytest.fixture
def mcp_server(manager):
    return create_mcp_server(manager)


def _parse_tool_result(result):
    content = result[0]

    if hasattr(content, "text"):
        return json.loads(content.text)
    elif hasattr(content, "content"):
        return json.loads(content.content)
    else:
        return json.loads(str(content))


@pytest.mark.asyncio
async def test_get_server_status_tool(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_status", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert "port" in response
        assert response["port"] == 8000

        if response["status"] == "running":
            assert response.get("type") == "external", (
                "If status is 'running' before start, it must be an external process"
            )
        else:
            assert response["status"] == "stopped"


@pytest.mark.asyncio
async def test_start_server_tool(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("start_server", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert "message" in response
        assert response["status"] in ["started", "error"]  # Could be error if port is in use


@pytest.mark.asyncio
async def test_nonexistent_server_tool(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_status", {"name": "nonexistent"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert response["status"] == "error"
        assert "not found" in response["message"]


@pytest.mark.asyncio
async def test_stop_server_tool_not_running(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("stop_server", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert "message" in response
        if response["status"] == "error":
            assert "Failed to kill external process" in response["message"]
        elif response["status"] == "not_running":
            assert "not running" in response["message"]
        else:
            pytest.fail(
                f"Unexpected status '{response['status']}' for a server not started by the test. \
                Message: '{response['message']}'"
            )


@pytest.mark.asyncio
async def test_stop_server_tool_running_process(mcp_server, manager):
    async with Client(mcp_server) as client:
        start_result = await client.call_tool("start_server", {"name": "test-server"})
        start_response = _parse_tool_result(start_result)

        if start_response["status"] == "started":
            stop_result = await client.call_tool("stop_server", {"name": "test-server"})

            assert len(stop_result) == 1

            stop_response = _parse_tool_result(stop_result)

            assert "status" in stop_response
            assert "message" in stop_response
            assert stop_response["status"] == "stopped"
            assert "stopped" in stop_response["message"]


@pytest.mark.asyncio
async def test_get_server_logs_tool(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_logs", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response

        assert response["status"] == "error"
        assert "not running" in response["message"]


@pytest.mark.asyncio
async def test_get_server_logs_with_lines_parameter(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_logs", {"name": "test-server", "lines": 100})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert response["status"] == "error"
        assert "not running" in response["message"]
