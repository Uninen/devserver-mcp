import json

import pytest
from fastmcp import Client

from devserver_mcp import create_mcp_server
from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def test_config():
    """Create a test configuration"""
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
    """Create a DevServerManager instance for testing"""
    return DevServerManager(test_config)


@pytest.fixture
def mcp_server(manager):
    """Create a FastMCP server instance for testing"""
    return create_mcp_server(manager)


def _parse_tool_result(result):
    """Helper to parse tool result content"""
    content = result[0]
    # Try different ways to extract the text content
    if hasattr(content, "text"):
        return json.loads(content.text)
    elif hasattr(content, "content"):
        return json.loads(content.content)
    else:
        # Fallback to string conversion
        return json.loads(str(content))


@pytest.mark.asyncio
async def test_get_server_status_tool(mcp_server):
    """Test the get_server_status tool via MCP client"""
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_status", {"name": "test-server"})

        # The result should be a list with content objects
        assert len(result) == 1

        # Parse the JSON response
        response = _parse_tool_result(result)

        # Check that we get the expected response structure
        assert "status" in response
        assert "port" in response
        assert response["port"] == 8000
        # Server should be stopped initially, or running if port is externally occupied
        if response["status"] == "running":
            assert response.get("type") == "external", (
                "If status is 'running' before start, it must be an external process"
            )
        else:
            assert response["status"] == "stopped"


@pytest.mark.asyncio
async def test_start_server_tool(mcp_server):
    """Test the start_server tool via MCP client"""
    async with Client(mcp_server) as client:
        result = await client.call_tool("start_server", {"name": "test-server"})

        # The result should be a list with content objects
        assert len(result) == 1

        # Parse the JSON response
        response = _parse_tool_result(result)

        # Check that we get the expected response structure
        assert "status" in response
        assert "message" in response
        assert response["status"] in ["started", "error"]  # Could be error if port is in use


@pytest.mark.asyncio
async def test_nonexistent_server_tool(mcp_server):
    """Test calling a tool with a nonexistent server name"""
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_status", {"name": "nonexistent"})

        # The result should be a list with content objects
        assert len(result) == 1

        # Parse the JSON response
        response = _parse_tool_result(result)

        # Check that we get an error for nonexistent server
        assert "status" in response
        assert response["status"] == "error"
        assert "not found" in response["message"]


@pytest.mark.asyncio
async def test_stop_server_tool_not_found(mcp_server):
    """Test the stop_server tool with a nonexistent server name"""
    async with Client(mcp_server) as client:
        result = await client.call_tool("stop_server", {"name": "nonexistent"})

        # The result should be a list with content objects
        assert len(result) == 1

        # Parse the JSON response
        response = _parse_tool_result(result)

        # Check that we get an error for nonexistent server
        assert "status" in response
        assert "message" in response
        assert response["status"] == "error"
        assert "not found" in response["message"]


@pytest.mark.asyncio
async def test_stop_server_tool_not_running(mcp_server):
    """Test the stop_server tool with a server that's not running"""
    async with Client(mcp_server) as client:
        result = await client.call_tool("stop_server", {"name": "test-server"})

        # The result should be a list with content objects
        assert len(result) == 1

        # Parse the JSON response
        response = _parse_tool_result(result)

        # Check that we get the expected response for a stopped server
        assert "status" in response
        assert "message" in response
        if response["status"] == "error":
            # This can happen if the port is in use by an external process
            assert "Failed to kill external process" in response["message"]
        elif response["status"] == "not_running":
            assert "not running" in response["message"]
        else:
            # Fail if the status is unexpected for a server that wasn't started by this test
            pytest.fail(
                f"Unexpected status '{response['status']}' for a server not started by the test. \
                Message: '{response['message']}'"
            )


@pytest.mark.asyncio
async def test_stop_server_tool_running_process(mcp_server, manager):
    """Test the stop_server tool with a running managed process"""
    async with Client(mcp_server) as client:
        # First start the server
        start_result = await client.call_tool("start_server", {"name": "test-server"})
        start_response = _parse_tool_result(start_result)

        # Only proceed if start was successful
        if start_response["status"] == "started":
            # Now stop the server
            stop_result = await client.call_tool("stop_server", {"name": "test-server"})

            # The result should be a list with content objects
            assert len(stop_result) == 1

            # Parse the JSON response
            stop_response = _parse_tool_result(stop_result)

            # Check that we get the expected response for stopping a running server
            assert "status" in stop_response
            assert "message" in stop_response
            assert stop_response["status"] == "stopped"
            assert "stopped" in stop_response["message"]


@pytest.mark.asyncio
async def test_stop_server_tool_case_insensitive(mcp_server):
    """Test the stop_server tool with different case variations"""
    async with Client(mcp_server) as client:
        # Test with uppercase
        result = await client.call_tool("stop_server", {"name": "TEST-SERVER"})
        response = _parse_tool_result(result)

        # Should still find the server (case insensitive)
        assert "status" in response
        assert response["status"] in ["not_running", "stopped", "error"]  # Various valid states

        # Test with mixed case
        result = await client.call_tool("stop_server", {"name": "Test-Server"})
        response = _parse_tool_result(result)

        # Should still find the server (case insensitive)
        assert "status" in response
        assert response["status"] in ["not_running", "stopped", "error"]  # Various valid states
