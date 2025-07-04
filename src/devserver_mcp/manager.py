import asyncio
import contextlib
import socket
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from devserver_mcp.process import ManagedProcess
from devserver_mcp.state import StateManager
from devserver_mcp.types import (
    Config,
    LogCallback,
    LogsResult,
    OperationStatus,
    ServerOperationResult,
    ServerStatus,
    ServerStatusEnum,
)
from devserver_mcp.utils import get_tool_emoji, log_error_to_file

SERVER_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta", "bright_yellow"]


class DevServerManager:
    def __init__(self, config: Config, project_path: str | None = None):
        self.config = config
        self.processes: dict[str, ManagedProcess] = {}
        self._log_callbacks: list[LogCallback] = []
        self._status_callbacks: list = []
        self._playwright_operator = None
        self._playwright_config_enabled = config.experimental and config.experimental.playwright
        self._playwright_init_error = None

        project_path = project_path or str(Path.cwd())
        self.state_manager = StateManager(project_path)
        self.state_manager.cleanup_dead()

        self._assign_colors()
        self._init_playwright_if_enabled()

    async def autostart_configured_servers(self):
        for name, process in self.processes.items():
            if process.config.autostart:
                server_status = self.get_server_status(name)
                if server_status["status"] == "stopped":  # Server is not running and port is not in use
                    await self.start_server(name)

        # Auto-start Playwright if enabled
        await self._autostart_playwright()

    def _assign_colors(self):
        for i, name in enumerate(self.config.servers.keys()):
            color = SERVER_COLORS[i % len(SERVER_COLORS)]
            config = self.config.servers[name]
            self.processes[name.lower()] = ManagedProcess(name, config, color, self.state_manager)

    def add_log_callback(self, callback: LogCallback):
        self._log_callbacks.append(callback)

    def add_status_callback(self, callback):
        self._status_callbacks.append(callback)

    async def _notify_log(self, server: str, timestamp: str, message: str):
        for callback in self._log_callbacks:
            with contextlib.suppress(Exception):
                result = callback(server, timestamp, message)
                if asyncio.iscoroutine(result):
                    await result

    def _notify_status_change(self):
        for callback in self._status_callbacks:
            with contextlib.suppress(Exception):
                callback()

    async def start_server(self, name: str) -> ServerOperationResult:
        process = self.processes.get(name.lower())
        if not process:
            return ServerOperationResult(status=OperationStatus.ERROR, message=f"Server '{name}' not found")

        if process.is_running:
            return ServerOperationResult(
                status=OperationStatus.ALREADY_RUNNING, message=f"Server '{name}' already running"
            )

        if self._is_port_in_use(process.config.port):
            return ServerOperationResult(status=OperationStatus.ERROR, message=f"Port {process.config.port} in use")

        success = await process.start(self._notify_log)
        self._notify_status_change()

        if success:
            return ServerOperationResult(status=OperationStatus.STARTED, message=f"Server '{name}' started")
        else:
            return ServerOperationResult(
                status=OperationStatus.ERROR, message=f"Failed to start '{name}': {process.error}"
            )

    async def stop_server(self, name: str) -> ServerOperationResult:
        process = self.processes.get(name.lower())
        if not process:
            return ServerOperationResult(status=OperationStatus.ERROR, message=f"Server '{name}' not found")

        if process.is_running:
            await process.stop()
            self._notify_status_change()
            return ServerOperationResult(status=OperationStatus.STOPPED, message=f"Server '{name}' stopped")

        if self._is_port_in_use(process.config.port):
            return ServerOperationResult(
                status=OperationStatus.ERROR,
                message=f"Failed to kill external process on port {process.config.port}",
            )

        return ServerOperationResult(status=OperationStatus.NOT_RUNNING, message=f"Server '{name}' not running")

    def get_server_status(self, name: str) -> dict:
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            return {
                "status": "running",
                "port": process.config.port,
                "command": process.config.command,
                "working_dir": process.config.working_dir,
            }
        elif self._is_port_in_use(process.config.port):
            return {
                "status": "external",
                "port": process.config.port,
                "message": "External process on port",
            }
        else:
            return {"status": "stopped", "port": process.config.port, "error": process.error}

    def get_devserver_logs(self, name: str, offset: int = 0, limit: int = 100, reverse: bool = True) -> LogsResult:
        process = self.processes.get(name.lower())
        if not process:
            return LogsResult(status="error", message=f"Server '{name}' not found")

        if not process.is_running:
            if self._is_port_in_use(process.config.port):
                return LogsResult(status="error", message="Cannot get logs for external process")
            else:
                return LogsResult(status="error", message="Server not running")

        log_lines, total, has_more = process.logs.get_range(offset, limit, reverse)
        return LogsResult(
            status="success",
            lines=log_lines,
            count=len(log_lines),
            total=total,
            offset=offset,
            has_more=has_more,
        )

    def get_devserver_statuses(self) -> list[ServerStatus]:
        servers = []
        for _name, process in self.processes.items():
            if process.is_running:
                status = ServerStatusEnum.RUNNING
            elif self._is_port_in_use(process.config.port):
                status = ServerStatusEnum.EXTERNAL
            else:
                status = ServerStatusEnum.STOPPED

            servers.append(
                ServerStatus(
                    name=process.name,
                    status=status,
                    port=process.config.port,
                    error=process.error,
                    color=process.color,
                )
            )
        return servers

    async def shutdown_all(self):
        stop_tasks = []
        for process in self.processes.values():
            if process.is_running:
                stop_tasks.append(process.stop())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        await self._shutdown_playwright()

        self._notify_status_change()

    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return False
            except OSError:
                return True

    def _init_playwright_if_enabled(self):
        if self._playwright_config_enabled:
            try:
                from devserver_mcp.playwright import PlaywrightOperator

                self._playwright_operator = PlaywrightOperator(headless=True)
            except Exception as e:
                self._playwright_init_error = f"Failed to initialize Playwright: {str(e)}"
                log_error_to_file(e, "Playwright initialization")
                self._playwright_operator = None

    async def _autostart_playwright(self):
        if self._playwright_config_enabled:
            if self._playwright_init_error:
                await self._notify_log(
                    f"{get_tool_emoji()} Playwright",
                    datetime.now().strftime("%H:%M:%S"),
                    f"Failed to initialize: {self._playwright_init_error}",
                )
                self._notify_status_change()
            elif self._playwright_operator and not self._playwright_operator.is_initialized:
                try:
                    await self._playwright_operator.initialize()
                    await self._notify_log(
                        f"{get_tool_emoji()} Playwright",
                        datetime.now().strftime("%H:%M:%S"),
                        "Browser started successfully",
                    )
                    self._notify_status_change()
                except Exception as e:
                    log_error_to_file(e, "Playwright autostart")
                    await self._notify_log(
                        f"{get_tool_emoji()} Playwright",
                        datetime.now().strftime("%H:%M:%S"),
                        f"Failed to start browser: {e}",
                    )
                    self._notify_status_change()

    async def _shutdown_playwright(self):
        if self._playwright_operator:
            try:
                await self._playwright_operator.close()
                self._notify_status_change()
            except Exception as e:
                log_error_to_file(e, "Playwright shutdown")
                self._notify_status_change()

    @property
    def playwright_enabled(self) -> bool:
        return bool(self._playwright_config_enabled)

    @property
    def playwright_running(self) -> bool:
        return self._playwright_operator is not None and self._playwright_operator.is_initialized

    async def playwright_navigate(
        self, url: str, wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "networkidle"
    ) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.navigate(url, wait_until)
            await self._notify_log(
                f"{get_tool_emoji()} Playwright", datetime.now().strftime("%H:%M:%S"), f"Navigated to {url}"
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_navigate")
            return {"status": "error", "message": str(e)}

    async def playwright_snapshot(self) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.snapshot()
            page_url = result.get("url", "unknown page")
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Captured accessibility snapshot of {page_url}",
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_snapshot")
            return {"status": "error", "message": str(e)}

    async def playwright_console_messages(
        self, clear: bool = False, offset: int = 0, limit: int = 100, reverse: bool = True
    ) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            messages, total, has_more = await self._playwright_operator.get_console_messages(
                clear, offset, limit, reverse
            )
            message_count = len(messages)
            clear_text = " and cleared" if clear else ""
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Retrieved {message_count} of {total} console messages{clear_text}",
            )
            return {
                "status": "success",
                "messages": messages,
                "count": message_count,
                "total": total,
                "offset": offset,
                "has_more": has_more,
            }
        except Exception as e:
            log_error_to_file(e, "playwright_console_messages")
            return {"status": "error", "message": str(e)}

    async def playwright_click(self, ref: str) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.click(ref)
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Clicked element: {ref}",
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_click")
            return {"status": "error", "message": str(e)}

    async def playwright_type(self, ref: str, text: str, submit: bool = False, slowly: bool = False) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.type(ref, text, submit, slowly)
            submit_text = " and submitted" if submit else ""
            slowly_text = " slowly" if slowly else ""
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Typed {len(text)} characters{slowly_text} into element: {ref}{submit_text}",
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_type")
            return {"status": "error", "message": str(e)}

    async def playwright_resize(self, width: int, height: int) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.resize(width, height)
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Resized viewport to {width}x{height}",
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_resize")
            return {"status": "error", "message": str(e)}

    async def playwright_screenshot(self, full_page: bool = False, name: str | None = None) -> dict[str, Any]:
        if not self._playwright_operator:
            return {"status": "error", "message": "Playwright not available"}

        try:
            result = await self._playwright_operator.screenshot(full_page, name)
            filepath = result.get("path", "unknown")
            full_page_text = " (full page)" if full_page else ""
            name_text = f" as '{name}'" if name else ""
            await self._notify_log(
                f"{get_tool_emoji()} Playwright",
                datetime.now().strftime("%H:%M:%S"),
                f"Screenshot saved to {filepath}{full_page_text}{name_text}",
            )
            return result
        except Exception as e:
            log_error_to_file(e, "playwright_screenshot")
            return {"status": "error", "message": str(e)}
