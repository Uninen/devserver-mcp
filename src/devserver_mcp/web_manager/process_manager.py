import asyncio
import logging
from typing import TYPE_CHECKING, Any

from devserver_mcp.log_storage import LogStorage
from devserver_mcp.process import ManagedProcess
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
            }

        process = self.processes[project_id][server_name]
        return {
            "name": server_name,
            "status": process.status,
            "pid": process.pid,
            "error": process.error,
        }

    def get_process_logs(
        self, project_id: str, server_name: str, offset: int = 0, limit: int = 100
    ) -> tuple[list[str], int, bool]:
        if project_id not in self.processes or server_name not in self.processes[project_id]:
            return [], 0, False

        process = self.processes[project_id][server_name]
        return process.logs.get_range(offset, limit, reverse=True)

    async def cleanup_all(self):
        logger.info("Cleaning up all processes...")
        tasks = []
        for project_id, project_processes in self.processes.items():
            for server_name, process in project_processes.items():
                if process.is_running:
                    logger.info(f"Stopping {project_id}/{server_name}")
                    tasks.append(process.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All processes cleaned up")
