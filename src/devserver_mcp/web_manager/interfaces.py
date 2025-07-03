from typing import Any, Protocol, runtime_checkable

from devserver_mcp.types import ServerConfig


@runtime_checkable
class ProcessManagerProtocol(Protocol):
    """Protocol for process management operations."""

    processes: dict[str, Any]

    def set_websocket_manager(self, websocket_manager: Any) -> None:
        """Set the WebSocket manager for real-time log streaming."""
        ...

    async def start_process(self, project_id: str, server_name: str, config: ServerConfig) -> bool:
        """Start a development server process."""
        ...

    async def stop_process(self, project_id: str, server_name: str) -> bool:
        """Stop a development server process."""
        ...

    def get_process_logs(
        self, project_id: str, server_name: str, offset: int, limit: int
    ) -> tuple[list[str] | None, int, bool]:
        """Get logs from a development server process."""
        ...

    def get_process_status(self, project_id: str, server_name: str) -> dict[str, Any]:
        """Get the status of a development server process."""
        ...

    async def start_idle_monitoring(self) -> None:
        """Start monitoring for idle processes."""
        ...

    async def cleanup_all(self) -> None:
        """Clean up all processes."""
        ...


@runtime_checkable
class WebSocketManagerProtocol(Protocol):
    """Protocol for WebSocket management operations."""

    async def connect(self, websocket: Any, project_id: str) -> str:
        """Connect a WebSocket client."""
        ...

    def disconnect(self, connection_id: str) -> None:
        """Disconnect a WebSocket client."""
        ...

    async def broadcast_to_project(self, project_id: str, message: dict[str, Any]) -> None:
        """Broadcast a message to all clients for a project."""
        ...
