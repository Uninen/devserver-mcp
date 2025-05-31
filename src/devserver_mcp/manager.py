import asyncio
import contextlib
import socket

from devserver_mcp.playwright_manager import PlaywrightManager
from devserver_mcp.process import ManagedProcess
from devserver_mcp.types import Config, LogCallback

SERVER_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta", "bright_yellow"]


class DevServerManager:
    def __init__(self, config: Config):
        self.config = config
        self.processes: dict[str, ManagedProcess] = {}
        self.playwright_manager: PlaywrightManager | None = None
        self._log_callbacks: list[LogCallback] = []
        self._status_callbacks: list = []
        self._assign_colors()

        if self.config.experimental_playwright:
            # Note: _notify_log is async, PlaywrightManager expects an async log_callback
            self.playwright_manager = PlaywrightManager(self.config, self._notify_log)
            # _notify_status_change is synchronous, PlaywrightManager expects an async status_callback
            # This might need adjustment in PlaywrightManager or here if issues arise.
            # For now, assuming PlaywrightManager's add_status_callback can handle sync or has an async wrapper.
            # If _notify_status_change needs to be async, we'll need to adjust its definition.
            # Let's assume for now it's okay, or PM handles it.
            # A better way would be to make _notify_status_change async if it performs async operations
            # or if PlaywrightManager strictly requires an async callback.
            # For this step, we'll proceed assuming current structure is acceptable.
            self.playwright_manager.add_status_callback(self._notify_status_change_async_wrapper)


    async def _notify_status_change_async_wrapper(self):
        # This wrapper makes the synchronous _notify_status_change callable by PlaywrightManager
        # if it expects an async callback. If _notify_status_change itself can be async,
        # this wrapper is not strictly needed.
        self._notify_status_change()


    async def autostart_configured_servers(self):
        for name, process in self.processes.items():
            if process.config.autostart:
                server_status = self.get_server_status(name)
                if server_status["status"] == "stopped":  # It implies not managed running and port not in use
                    await self.start_server(name)
        if self.playwright_manager and self.config.experimental_playwright:
            await self.playwright_manager.launch_browser()

    def _assign_colors(self):
        for i, name in enumerate(self.config.servers.keys()):
            color = SERVER_COLORS[i % len(SERVER_COLORS)]
            config = self.config.servers[name]
            self.processes[name.lower()] = ManagedProcess(name, config, color)

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

    async def start_server(self, name: str) -> dict:
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            return {"status": "already_running", "message": f"Server '{name}' already running"}

        if self._is_port_in_use(process.config.port):
            return {"status": "error", "message": f"Port {process.config.port} in use"}

        success = await process.start(self._notify_log)
        self._notify_status_change()

        if success:
            return {"status": "started", "message": f"Server '{name}' started"}
        else:
            return {"status": "error", "message": f"Failed to start '{name}': {process.error}"}

    async def stop_server(self, name: str) -> dict:
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            await process.stop()
            self._notify_status_change()
            return {"status": "stopped", "message": f"Server '{name}' stopped"}

        if self._is_port_in_use(process.config.port):
            return {"status": "error", "message": f"Failed to kill external process on port {process.config.port}"}

        return {"status": "not_running", "message": f"Server '{name}' not running"}

    def get_server_status(self, name: str) -> dict:
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            return {
                "status": "running",
                "type": "managed",
                "port": process.config.port,
                "command": process.config.command,
                "working_dir": process.config.working_dir,
            }
        elif self._is_port_in_use(process.config.port):
            return {
                "status": "running",
                "type": "external",
                "port": process.config.port,
                "message": "External process on port",
            }
        else:
            return {"status": "stopped", "type": "none", "port": process.config.port, "error": process.error}

    def get_server_logs(self, name: str, lines: int = 500) -> dict:
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if not process.is_running:
            if self._is_port_in_use(process.config.port):
                return {"status": "error", "message": "Cannot get logs for external process"}
            else:
                return {"status": "error", "message": "Server not running"}

        log_lines = list(process.logs)[-lines:]
        return {"status": "success", "lines": log_lines, "count": len(log_lines)}

    def get_all_servers(self) -> list[dict]:
        servers = []
        for _name, process in self.processes.items():
            external_running = not process.is_running and self._is_port_in_use(process.config.port)

            servers.append(
                {
                    "name": process.name,
                    "status": process.status,
                    "port": process.config.port,
                    "error": process.error,
                    "external_running": external_running,
                    "color": process.color,
                }
            )

        if self.playwright_manager and self.config.experimental_playwright:
            playwright_status = {
                **self.playwright_manager.get_status(),
                "color": "bright_blue",  # Default color for Playwright
            }
            servers.insert(0, playwright_status)
        return servers

    async def shutdown_all(self):
        stop_tasks = []
        for process in self.processes.values():
            if process.is_running:
                stop_tasks.append(process.stop())

        if self.playwright_manager:
            stop_tasks.append(self.playwright_manager.close_browser())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        self._notify_status_change()

    def _is_port_in_use(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("localhost", port))
                return False
            except OSError:
                return True
