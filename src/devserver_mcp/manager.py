import asyncio
import contextlib
import os
import socket
import sys
import time
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import datetime

from pydantic import BaseModel

SERVER_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta", "bright_yellow"]

LogCallback = Callable[[str, str, str], None] | Callable[[str, str, str], Awaitable[None]]


class ServerConfig(BaseModel):
    """Configuration for a single dev server"""

    command: str
    working_dir: str = "."
    port: int


class Config(BaseModel):
    """Overall configuration"""

    servers: dict[str, ServerConfig]


class ManagedProcess:
    """Represents a process managed by the dev server"""

    def __init__(self, name: str, config: ServerConfig, color: str):
        self.name = name
        self.config = config
        self.color = color
        self.process: asyncio.subprocess.Process | None = None
        self.logs: deque = deque(maxlen=500)
        self.start_time: float | None = None
        self.error: str | None = None

    async def start(self, log_callback: LogCallback) -> bool:
        """Start the managed process"""
        try:
            self.error = None
            self.start_time = time.time()

            work_dir = os.path.expanduser(self.config.working_dir)
            work_dir = os.path.abspath(work_dir)

            self.process = await asyncio.create_subprocess_shell(
                self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )

            asyncio.create_task(self._read_output(log_callback))
            await asyncio.sleep(0.5)

            if self.process.returncode is not None:
                self.error = f"Process exited immediately with code {self.process.returncode}"
                return False

            return True

        except Exception as e:
            self.error = str(e)
            return False

    async def _read_output(self, log_callback: LogCallback):
        """Read process output and forward to callback"""
        while self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    self.logs.append(decoded)
                    # Handle both sync and async callbacks
                    result = log_callback(self.name, timestamp, decoded)
                    if asyncio.iscoroutine(result):
                        await result

            except Exception:
                break

    def stop(self):
        """Stop the managed process immediately"""
        if self.process and self.process.pid is not None:
            try:
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    import signal

                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass
            finally:
                self.process = None
                self.start_time = None

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    @property
    def uptime(self) -> int | None:
        if not self.is_running or not self.start_time:
            return None
        return int(time.time() - self.start_time)

    @property
    def status(self) -> str:
        if self.is_running:
            return "running"
        elif self.error:
            return "error"
        else:
            return "stopped"


class DevServerManager:
    """Core business logic for managing development servers"""

    def __init__(self, config: Config):
        self.config = config
        self.processes: dict[str, ManagedProcess] = {}
        self._log_callbacks: list[LogCallback] = []
        self._status_callbacks: list[Callable[[], None]] = []
        self._assign_colors()

    def _assign_colors(self):
        """Assign colors to servers"""
        for i, name in enumerate(self.config.servers.keys()):
            color = SERVER_COLORS[i % len(SERVER_COLORS)]
            config = self.config.servers[name]
            self.processes[name.lower()] = ManagedProcess(name, config, color)

    def add_log_callback(self, callback: LogCallback):
        """Add callback for log events"""
        self._log_callbacks.append(callback)

    def add_status_callback(self, callback: Callable[[], None]):
        """Add callback for status change events"""
        self._status_callbacks.append(callback)

    async def _notify_log(self, server: str, timestamp: str, message: str):
        """Notify all log callbacks"""
        for callback in self._log_callbacks:
            with contextlib.suppress(Exception):
                result = callback(server, timestamp, message)
                if asyncio.iscoroutine(result):
                    await result

    def _notify_status_change(self):
        """Notify all status callbacks"""
        for callback in self._status_callbacks:
            with contextlib.suppress(Exception):
                callback()

    async def start_server(self, name: str) -> dict:
        """Start a configured development server"""
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            return {"status": "already_running", "message": f"Server '{name}' running"}

        if self._is_port_in_use(process.config.port):
            return {"status": "error", "message": f"Port {process.config.port} in use"}

        success = await process.start(self._notify_log)
        self._notify_status_change()

        if success:
            return {"status": "started", "message": f"Server '{name}' started"}
        else:
            return {"status": "error", "message": f"Failed to start '{name}': {process.error}"}

    async def stop_server(self, name: str) -> dict:
        """Stop a running server (managed or external)"""
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            process.stop()
            self._notify_status_change()
            return {"status": "stopped", "message": f"Server '{name}' stopped"}

        if self._is_port_in_use(process.config.port):
            if self._kill_port_process(process.config.port):
                self._notify_status_change()
                return {"status": "stopped", "message": f"External on port {process.config.port} killed"}
            else:
                return {"status": "error", "message": f"Failed to kill external on port {process.config.port}"}

        return {"status": "not_running", "message": f"Server '{name}' not running"}

    def get_server_status(self, name: str) -> dict:
        """Get the status of a server"""
        process = self.processes.get(name.lower())
        if not process:
            return {"status": "error", "message": f"Server '{name}' not found"}

        if process.is_running:
            return {
                "status": "running",
                "type": "managed",
                "port": process.config.port,
                "uptime_seconds": process.uptime,
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
        """Get recent log output from a managed server"""
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
        """Get status of all servers"""
        servers = []
        for _name, process in self.processes.items():
            external_running = not process.is_running and self._is_port_in_use(process.config.port)

            servers.append(
                {
                    "name": process.name,
                    "status": process.status,
                    "port": process.config.port,
                    "uptime": process.uptime,
                    "error": process.error,
                    "external_running": external_running,
                    "color": process.color,
                }
            )
        return servers

    def shutdown_all(self):
        """Shutdown all managed processes immediately"""
        for process in self.processes.values():
            if process.is_running:
                process.stop()
        self._notify_status_change()

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def _kill_port_process(self, port: int) -> bool:
        """Attempt to kill process using a port"""
        try:
            if sys.platform == "darwin" or sys.platform.startswith("linux"):
                import subprocess

                result = subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, capture_output=True)
                return result.returncode == 0
            else:
                return False
        except Exception:
            return False
