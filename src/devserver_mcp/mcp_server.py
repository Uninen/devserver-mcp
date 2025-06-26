from datetime import datetime
from typing import Any, Literal

from fastmcp import FastMCP

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import (
    LogsResult,
    ServerOperationResult,
    ServerStatus,
)
from devserver_mcp.utils import get_tool_emoji, log_error_to_file


def create_mcp_server(manager: DevServerManager) -> FastMCP:
    mcp = FastMCP("devserver")

    @mcp.tool
    async def start_server(name: str) -> ServerOperationResult:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'start_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.start_server(name)

    @mcp.tool
    async def stop_server(name: str) -> ServerOperationResult:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'stop_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.stop_server(name)

    @mcp.tool
    async def get_devserver_logs(name: str, offset: int = 0, limit: int = 100, reverse: bool = True) -> LogsResult:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_devserver_logs' called with: "
            f"{{'name': {repr(name)}, 'offset': {offset}, 'limit': {limit}, 'reverse': {reverse}}}",
        )
        return manager.get_devserver_logs(name, offset, limit, reverse)

    @mcp.tool
    async def get_devserver_statuses() -> list[ServerStatus]:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            "Tool 'get_devserver_statuses' called",
        )
        return manager.get_devserver_statuses()

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
    async def browser_console_messages(
        clear: bool = False, offset: int = 0, limit: int = 100, reverse: bool = True
    ) -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_console_messages' called with: "
            f"{{'clear': {clear}, 'offset': {offset}, 'limit': {limit}, 'reverse': {reverse}}}",
        )
        try:
            return await manager.playwright_console_messages(clear, offset, limit, reverse)
        except Exception as e:
            log_error_to_file(e, "browser_console_messages")
            return {"status": "error", "message": str(e)}

    @mcp.tool
    async def browser_click(ref: str) -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_click' called with: {{'ref': {repr(ref)}}}",
        )
        try:
            return await manager.playwright_click(ref)
        except Exception as e:
            log_error_to_file(e, "browser_click")
            return {"status": "error", "message": str(e)}

    @mcp.tool
    async def browser_type(ref: str, text: str, submit: bool = False, slowly: bool = False) -> dict[str, Any]:
        text_preview = text[:20] + "..." if len(text) > 20 else text
        params = f"{{'ref': {repr(ref)}, 'text': {repr(text_preview)}, 'submit': {submit}, 'slowly': {slowly}}}"
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_type' called with: {params}",
        )
        try:
            return await manager.playwright_type(ref, text, submit, slowly)
        except Exception as e:
            log_error_to_file(e, "browser_type")
            return {"status": "error", "message": str(e)}

    @mcp.tool
    async def browser_resize(width: int, height: int) -> dict[str, Any]:
        await manager._notify_log(
            f"{get_tool_emoji()} Playwright",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'browser_resize' called with: {{'width': {width}, 'height': {height}}}",
        )
        try:
            return await manager.playwright_resize(width, height)
        except Exception as e:
            log_error_to_file(e, "browser_resize")
            return {"status": "error", "message": str(e)}
