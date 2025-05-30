"""Tests for MCP server functionality"""

import json

import pytest
from fastmcp import Client

from devserver_mcp import Config, DevServerManager, ServerConfig, create_mcp_server


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
        assert response["status"] == "stopped"  # Server should be stopped initially


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
