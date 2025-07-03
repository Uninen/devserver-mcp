import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from devserver_mcp.cleanup import cleanup_orphaned_processes
from devserver_mcp.log_storage import LogStorage
from devserver_mcp.process import ManagedProcess
from devserver_mcp.settings import load_settings
from devserver_mcp.state import StateManager
from devserver_mcp.types import ServerConfig

# Import TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from devserver_mcp.web_manager.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class WebManagedProcess(ManagedProcess):
    def __init__(self, name: str, config: ServerConfig, color: str, state_manager: StateManager):
        super().__init__(name, config, color, state_manager)
        self.logs = LogStorage(max_lines=1000)


class ProcessManager:
    def __init__(self):
        self.processes: dict[str, dict[str, WebManagedProcess]] = {}
        self._shutdown_event = asyncio.Event()
        self.websocket_manager: WebSocketManager | None = None
        self._idle_monitor_task: asyncio.Task | None = None
        self.settings = load_settings()

        # Clean up orphaned processes on startup
        self._cleanup_orphaned_on_startup()

    def _cleanup_orphaned_on_startup(self):
        """Clean up any orphaned processes from previous runs."""
        try:
            cleaned = cleanup_orphaned_processes()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} orphaned processes from previous runs")
        except Exception as e:
            logger.error(f"Error during orphaned process cleanup: {e}")

    def set_websocket_manager(self, websocket_manager: "WebSocketManager"):
        """Set the WebSocket manager for real-time log streaming."""
        self.websocket_manager = websocket_manager

    async def start_process(
        self, project_id: str, server_name: str, config: ServerConfig, color: str = "#FFFFFF"
    ) -> bool:
        if project_id not in self.processes:
            self.processes[project_id] = {}

        if server_name in self.processes[project_id]:
            process = self.processes[project_id][server_name]
            if process.is_running:
                logger.info(f"Process {project_id}/{server_name} is already running")
                return True

        state_manager = StateManager(project_id)
        process = WebManagedProcess(server_name, config, color, state_manager)
        self.processes[project_id][server_name] = process

        async def log_callback(server_name: str, timestamp: str, line: str):
            # Send log to WebSocket clients if manager is available
            if self.websocket_manager:
                await self.websocket_manager.send_log(project_id, server_name, timestamp, line)

        success = await process.start(log_callback)
        if success:
            logger.info(f"Started process {project_id}/{server_name} with PID {process.pid}")
            # Notify WebSocket clients of status change
            if self.websocket_manager:
                await self.websocket_manager.send_server_status(project_id, server_name, "running", process.pid)
        else:
            logger.error(f"Failed to start process {project_id}/{server_name}: {process.error}")
            # Notify WebSocket clients of error
            if self.websocket_manager:
                await self.websocket_manager.send_server_status(project_id, server_name, "error", None)

        return success

    async def stop_process(self, project_id: str, server_name: str) -> bool:
        if project_id not in self.processes or server_name not in self.processes[project_id]:
            logger.warning(f"Process {project_id}/{server_name} not found")
            return False

        process = self.processes[project_id][server_name]
        if not process.is_running:
            logger.info(f"Process {project_id}/{server_name} is not running")
            return True

        await process.stop()
        logger.info(f"Stopped process {project_id}/{server_name}")
        # Notify WebSocket clients of status change
        if self.websocket_manager:
            await self.websocket_manager.send_server_status(project_id, server_name, "stopped", None)
        return True

    def get_process_status(self, project_id: str, server_name: str) -> dict[str, Any]:
        if project_id not in self.processes or server_name not in self.processes[project_id]:
            return {
                "name": server_name,
                "status": "stopped",
                "pid": None,
                "error": None,
                "idle_time": None,
            }

        process = self.processes[project_id][server_name]
        return {
            "name": server_name,
            "status": process.status,
            "pid": process.pid,
            "error": process.error,
            "idle_time": process.idle_time,
        }

    def get_process_logs(
        self, project_id: str, server_name: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[str], int, bool]:
        if project_id not in self.processes or server_name not in self.processes[project_id]:
            return [], 0, False

        process = self.processes[project_id][server_name]
        return process.logs.get_range(offset, limit, reverse=True)

    async def start_idle_monitoring(self):
        """Start the idle monitoring background task."""
        if self._idle_monitor_task is None or self._idle_monitor_task.done():
            self._idle_monitor_task = asyncio.create_task(self._monitor_idle_processes())
            logger.info("Started idle process monitoring")

    async def stop_idle_monitoring(self):
        """Stop the idle monitoring background task."""
        if self._idle_monitor_task and not self._idle_monitor_task.done():
            self._idle_monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._idle_monitor_task
            logger.info("Stopped idle process monitoring")

    async def _monitor_idle_processes(self):
        """Background task to monitor and stop idle processes."""
        while not self._shutdown_event.is_set():
            try:
                # Check every 30 seconds
                await asyncio.sleep(30)

                # Reload settings in case they changed
                self.settings = load_settings()

                # Skip if global idle timeout is disabled
                if self.settings.idle_timeout == 0:
                    continue

                # Check all processes for idle timeout
                for project_id, project_processes in list(self.processes.items()):
                    # Get project-specific timeout if configured
                    project_timeout = self.settings.idle_timeout  # Default to global
                    for project_settings in self.settings.projects:
                        if project_settings.id == project_id and project_settings.idle_timeout > 0:
                            project_timeout = project_settings.idle_timeout
                            break

                    # Skip if project has timeout disabled
                    if project_timeout == 0:
                        continue

                    timeout_seconds = project_timeout * 60  # Convert minutes to seconds

                    for server_name, process in list(project_processes.items()):
                        if process.is_running and process.idle_time is not None and process.idle_time > timeout_seconds:
                            logger.info(
                                f"Stopping idle server {project_id}/{server_name} "
                                f"(idle for {process.idle_time:.0f} seconds)"
                            )
                            await self.stop_process(project_id, server_name)

            except Exception as e:
                logger.error(f"Error in idle monitoring task: {e}")

    async def cleanup_all(self):
        logger.info("Cleaning up all processes...")

        # Signal shutdown to stop monitoring
        self._shutdown_event.set()

        # Stop idle monitoring first
        await self.stop_idle_monitoring()

        tasks = []
        for project_id, project_processes in self.processes.items():
            for server_name, process in project_processes.items():
                if process.is_running:
                    logger.info(f"Stopping {project_id}/{server_name}")
                    tasks.append(process.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All processes cleaned up")
