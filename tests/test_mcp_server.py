import json

import pytest
from unittest.mock import AsyncMock
from fastmcp import Client

from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.playwright_manager import PlaywrightManager


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
async def playwright_manager():
    config = Config(servers={})  # Minimal config with required servers field
    log_callback = AsyncMock()
    pm = PlaywrightManager(config=config, log_callback=log_callback)
    yield pm
    if pm.browser:  # Changed from pm._browser to pm.browser
        await pm.close_browser()


@pytest.fixture
def mcp_server(manager, playwright_manager):
    return create_mcp_server(manager, playwright_manager)


def _parse_tool_result(result):
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
    async with Client(mcp_server) as client:
        result = await client.call_tool("get_server_status", {"name": "test-server"})

        assert len(result) == 1

        response = _parse_tool_result(result)

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
    async with Client(mcp_server) as client:
        start_result = await client.call_tool("start_server", {"name": "test-server"})
        start_response = _parse_tool_result(start_result)

        # Only proceed if start was successful
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
        # Should be error since server is not running
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


@pytest.mark.asyncio
async def test_browser_navigate_tool(mcp_server, playwright_manager: PlaywrightManager):  # Added playwright_manager
    async with Client(mcp_server) as client:
        url = "data:text/html,<h1>Navigate Test</h1>"
        # Clear mock calls before the action we're testing
        playwright_manager.log_callback.reset_mock()

        result = await client.call_tool("browser_navigate", {"url": url})

        assert len(result) == 1
        response = _parse_tool_result(result)

        assert response.get("status") == "success"
        assert response.get("message") == f"Navigated to {url}"


@pytest.mark.asyncio
async def test_browser_console_messages_tool(mcp_server):
    async with Client(mcp_server) as client:
        url = "data:text/html,<script>console.log('test console message');</script>"
        # Navigate to the page that generates the console message
        nav_result = await client.call_tool("browser_navigate", {"url": url})
        nav_response = _parse_tool_result(nav_result)
        assert nav_response.get("status") == "success", "Navigation failed before checking console messages"

        # Get console messages
        result = await client.call_tool("browser_console_messages", {})
        response = _parse_tool_result(result)

        assert response.get("status") == "success"
        assert "messages" in response
        assert "test console message" in response["messages"]


@pytest.mark.asyncio
async def test_browser_snapshot_tool(mcp_server):
    async with Client(mcp_server) as client:
        url = "data:text/html,<h1>Snapshot Test</h1>"
        # Navigate to the page
        nav_result = await client.call_tool("browser_navigate", {"url": url})
        nav_response = _parse_tool_result(nav_result)
        assert nav_response.get("status") == "success", "Navigation failed before taking snapshot"

        # Get accessibility snapshot
        result = await client.call_tool("browser_snapshot", {})
        response = _parse_tool_result(result)

        assert response.get("status") == "success"
        assert "snapshot" in response
        snapshot = response["snapshot"]
        assert snapshot is not None
        assert isinstance(snapshot, dict)  # Playwright returns a dict for the root object

        # Check for typical root ax object properties
        assert "role" in snapshot
        assert "name" in snapshot # The name of the document/WebArea
        assert "children" in snapshot # Should have children, one of which is the heading

        # Verify the heading is in the snapshot
        heading_found = False
        if "children" in snapshot and isinstance(snapshot["children"], list):
            for child in snapshot["children"]:
                if child.get("role") == "heading" and child.get("name") == "Snapshot Test":
                    heading_found = True
                    break
        assert heading_found, "Heading 'Snapshot Test' not found in accessibility tree"
