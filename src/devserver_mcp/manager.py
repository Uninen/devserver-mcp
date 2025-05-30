import asyncio
import contextlib
import socket

from devserver_mcp.process import ManagedProcess
from devserver_mcp.types import Config, LogCallback

SERVER_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta", "bright_yellow"]


class DevServerManager:
    def __init__(self, config: Config):
        self.config = config
        self.processes: dict[str, ManagedProcess] = {}
        self._log_callbacks: list[LogCallback] = []
        self._status_callbacks: list = []
        self._assign_colors()

    async def autostart_configured_servers(self):
        for name, process in self.processes.items():
            if process.config.autostart:
                server_status = self.get_server_status(name)
                if server_status["status"] == "stopped":  # It implies not managed running and port not in use
                    await self.start_server(name)

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
        return servers

    async def shutdown_all(self):
        stop_tasks = []
        for process in self.processes.values():
            if process.is_running:
                stop_tasks.append(process.stop())

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
