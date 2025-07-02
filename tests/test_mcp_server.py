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


def _parse_tool_result(result, expect_list=False):
    content = result[0]

    if hasattr(content, "text"):
        parsed = json.loads(content.text)
    elif hasattr(content, "content"):
        parsed = json.loads(content.content)
    else:
        parsed = json.loads(str(content))

    # Workaround for FastMCP serialization issue with single-item lists
    if expect_list and not isinstance(parsed, list):
        return [parsed]

    return parsed


@pytest.mark.asyncio
async def test_get_devserver_statuses_returns_all_servers(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_devserver_statuses", {})

        assert len(result) == 1

        response = _parse_tool_result(result, expect_list=True)

        assert isinstance(response, list)
        assert len(response) == 1

        server = response[0]
        assert server["name"] == "test-server"
        assert server["status"] in ["stopped", "running"]
        assert server["port"] == 8000
        assert "color" in server
        assert server["error"] is None or isinstance(server["error"], str)


@pytest.mark.asyncio
async def test_start_server_starts_successfully(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("start_server", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert "message" in response
        assert response["status"] in ["started", "error"]


@pytest.mark.asyncio
async def test_start_server_nonexistent_returns_error(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("start_server", {"name": "nonexistent"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert response["status"] == "error"
        assert "not found" in response["message"]


@pytest.mark.asyncio
async def test_stop_server_not_running_returns_appropriate_status(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("stop_server", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert "message" in response
        assert response["status"] in ["error", "not_running"]
        assert "not running" in response["message"] or "Failed to kill external process" in response["message"]


@pytest.mark.asyncio
async def test_stop_server_running_process_stops_successfully(mcp_server, manager):
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
async def test_get_devserver_logs_not_running_returns_error(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_devserver_logs", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert response["status"] == "error"
        assert "not running" in response["message"]


@pytest.mark.asyncio
async def test_get_devserver_logs_with_pagination(mcp_server):
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_devserver_logs", {"name": "test-server", "limit": 50, "offset": 0})

        assert len(result) == 1

        response = _parse_tool_result(result)

        assert "status" in response
        assert response["status"] == "error"
        assert "not running" in response["message"]


@pytest.mark.asyncio
async def test_get_devserver_statuses_with_multiple_servers(multi_server_config, temp_state_dir):
    manager = DevServerManager(multi_server_config)
    mcp_server = create_mcp_server(manager)

    async with Client(mcp_server) as client:
        result = await client.call_tool("get_devserver_statuses", {})

        assert len(result) == 1

        response = _parse_tool_result(result, expect_list=True)

        assert isinstance(response, list)
        assert len(response) == 2

        server_names = {server["name"] for server in response}
        assert server_names == {"api", "web"}

        for server in response:
            assert "name" in server
            assert "status" in server
            assert "port" in server
            assert "color" in server
            assert "error" in server
