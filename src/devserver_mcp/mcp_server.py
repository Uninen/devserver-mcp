from datetime import datetime

from fastmcp import FastMCP

from devserver_mcp.manager import DevServerManager
from devserver_mcp.playwright_manager import PlaywrightManager


def create_mcp_server(manager: DevServerManager, playwright_manager: PlaywrightManager | None = None) -> FastMCP:
    mcp = FastMCP("devserver")

    async def start_server_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'start_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.start_server(name)

    async def stop_server_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'stop_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.stop_server(name)

    async def get_server_status_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_status' called with: {{'name': {repr(name)}}}",
        )
        return manager.get_server_status(name)

    async def get_server_logs_with_logging(name: str, lines: int = 500) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_logs' called with: {{'name': {repr(name)}, 'lines': {lines}}}",
        )
        return manager.get_server_logs(name, lines)

    mcp.add_tool(start_server_with_logging, name="start_server")
    mcp.add_tool(stop_server_with_logging, name="stop_server")
    mcp.add_tool(get_server_status_with_logging, name="get_server_status")
    mcp.add_tool(get_server_logs_with_logging, name="get_server_logs")

    if playwright_manager:

        async def browser_navigate_with_logging(url: str) -> dict:
            await manager._notify_log(
                "MCP Server",
                datetime.now().strftime("%H:%M:%S"),
                f"Tool 'browser_navigate' called with: {{'url': {repr(url)}}}",
            )
            return await playwright_manager.browser_navigate(url)

        async def browser_snapshot_with_logging() -> dict:
            await manager._notify_log(
                "MCP Server",
                datetime.now().strftime("%H:%M:%S"),
                "Tool 'browser_snapshot' called",
            )
            return await playwright_manager.browser_snapshot()

        async def browser_console_messages_with_logging() -> dict:
            await manager._notify_log(
                "MCP Server",
                datetime.now().strftime("%H:%M:%S"),
                "Tool 'browser_console_messages' called",
            )
            return await playwright_manager.browser_console_messages()

        mcp.add_tool(browser_navigate_with_logging, name="browser_navigate")
        mcp.add_tool(browser_snapshot_with_logging, name="browser_snapshot")
        mcp.add_tool(browser_console_messages_with_logging, name="browser_console_messages")

    return mcp
