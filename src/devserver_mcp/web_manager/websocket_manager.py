import asyncio
import contextlib
import logging
import uuid

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time log streaming."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.project_connections: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, project_id: str) -> str:
        """Register a new WebSocket connection."""
        try:
            connection_id = str(uuid.uuid4())

            async with self._lock:
                self.active_connections[connection_id] = websocket

                if project_id not in self.project_connections:
                    self.project_connections[project_id] = set()
                self.project_connections[project_id].add(connection_id)

            logger.info(f"WebSocket connected: {connection_id} for project {project_id}")
            return connection_id
        except Exception as e:
            logger.error(f"Failed to register WebSocket connection for project {project_id}: {e}")
            raise

    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection."""
        try:
            asyncio.create_task(self._disconnect(connection_id))
        except Exception as e:
            logger.error(f"Error scheduling disconnect for {connection_id}: {e}")

    async def _disconnect(self, connection_id: str):
        """Internal async disconnect handler."""
        try:
            async with self._lock:
                if connection_id in self.active_connections:
                    # Try to close the websocket gracefully
                    websocket = self.active_connections[connection_id]
                    with contextlib.suppress(Exception):
                        await websocket.close()  # WebSocket may already be closed

                    del self.active_connections[connection_id]

                    # Remove from project connections
                    for project_id, connections in list(self.project_connections.items()):
                        if connection_id in connections:
                            connections.remove(connection_id)
                            if not connections:
                                del self.project_connections[project_id]
                            break

                    logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect for {connection_id}: {e}")

    async def send_log(self, project_id: str, server_name: str, timestamp: str, line: str):
        """Send a log line to all connections watching a specific project."""
        try:
            message = {"type": "log", "server_name": server_name, "timestamp": timestamp, "line": line}
            await self._broadcast_to_project(project_id, message)
        except Exception as e:
            logger.error(f"Failed to send log for {project_id}/{server_name}: {e}")

    async def send_server_status(self, project_id: str, server_name: str, status: str, pid: int | None = None):
        """Send server status update to all connections watching a specific project."""
        try:
            message = {"type": "status", "server_name": server_name, "status": status, "pid": pid}
            await self._broadcast_to_project(project_id, message)
        except Exception as e:
            logger.error(f"Failed to send status update for {project_id}/{server_name}: {e}")

    async def _broadcast_to_project(self, project_id: str, message: dict):
        """Broadcast a message to all connections watching a specific project."""
        try:
            async with self._lock:
                if project_id not in self.project_connections:
                    return

                # Create a list of connection IDs to avoid modification during iteration
                connection_ids = list(self.project_connections[project_id])

            # Send messages without holding the lock
            disconnected = []
            for connection_id in connection_ids:
                try:
                    websocket = self.active_connections.get(connection_id)
                    if websocket:
                        await websocket.send_json(message)
                except ConnectionError:
                    logger.debug(f"WebSocket {connection_id} disconnected")
                    disconnected.append(connection_id)
                except asyncio.CancelledError:
                    raise  # Let cancellation propagate
                except Exception as e:
                    logger.error(f"Unexpected error sending to WebSocket {connection_id}: {e}")
                    disconnected.append(connection_id)

            # Clean up disconnected connections
            for connection_id in disconnected:
                await self._disconnect(connection_id)

        except asyncio.CancelledError:
            raise  # Let cancellation propagate
        except Exception as e:
            logger.error(f"Error broadcasting to project {project_id}: {e}")
