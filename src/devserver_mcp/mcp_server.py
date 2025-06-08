from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from devserver_mcp.manager import DevServerManager
from devserver_mcp.utils import get_tool_emoji, log_error_to_file


def create_mcp_server(manager: DevServerManager) -> FastMCP:
    mcp = FastMCP("devserver")

    @mcp.tool
    async def start_server(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'start_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.start_server(name)

    @mcp.tool
    async def stop_server(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'stop_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.stop_server(name)

    @mcp.tool
    async def get_server_status(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_status' called with: {{'name': {repr(name)}}}",
        )
        return manager.get_server_status(name)

    @mcp.tool
    async def get_server_logs(name: str, lines: int = 500) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_logs' called with: {{'name': {repr(name)}, 'lines': {lines}}}",
        )
        return manager.get_server_logs(name, lines)

    if manager.config.experimental and manager.config.experimental.playwright:
        _add_playwright_commands(mcp, manager)

    return mcp


def _add_playwright_commands(mcp: FastMCP, manager: DevServerManager) -> None:
    @mcp.tool
    async def browser_navigate(
        url: str, wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "networkidle"
    ) -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_navigate' called with: {{'url': {repr(url)}, 'wait_until': {repr(wait_until)}}}",
        )
        try:
            return await manager.playwright_navigate(url, wait_until)
        except Exception as e:
            log_error_to_file(e, "browser_navigate")
            return {"status": "error", "message": str(e)}

    @mcp.tool
    async def browser_snapshot() -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            "Tool 'browser_snapshot' called",
        )
        try:
            return await manager.playwright_snapshot()
        except Exception as e:
            log_error_to_file(e, "browser_snapshot")
            return {"status": "error", "message": str(e)}

    @mcp.tool
    async def browser_console_messages(clear: bool = False) -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_console_messages' called with: {{'clear': {clear}}}",
        )
        try:
            return await manager.playwright_console_messages(clear)
        except Exception as e:
            log_error_to_file(e, "browser_console_messages")
            return {"status": "error", "message": str(e)}
