import asyncio
import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from devserver_mcp.web_manager.websocket_manager import WebSocketManager


@pytest.fixture
def websocket_manager():
    return WebSocketManager()


@pytest.fixture
def mock_websocket():
    """Mock WebSocket at the system boundary."""
    ws = MagicMock(spec=WebSocket)
    ws.client_state = WebSocketState.CONNECTED
    ws.send_json = MagicMock(return_value=asyncio.Future())
    ws.send_json.return_value.set_result(None)
    ws.close = MagicMock(return_value=asyncio.Future())
    ws.close.return_value.set_result(None)
    return ws


@pytest.mark.asyncio
async def test_connect_websocket_for_project(websocket_manager, mock_websocket):
    """Test connecting a WebSocket for project log streaming."""
    connection_id = await websocket_manager.connect(mock_websocket, "test-project")
    
    assert connection_id is not None
    assert len(websocket_manager.active_connections) == 1
    assert connection_id in websocket_manager.active_connections
    assert "test-project" in websocket_manager.project_connections


@pytest.mark.asyncio
async def test_disconnect_websocket_removes_connection(websocket_manager, mock_websocket):
    """Test disconnecting a WebSocket removes it from tracking."""
    connection_id = await websocket_manager.connect(mock_websocket, "test-project")
    
    # Disconnect
    websocket_manager.disconnect(connection_id)
    
    assert connection_id not in websocket_manager.active_connections
    assert "test-project" not in websocket_manager.project_connections


@pytest.mark.asyncio
async def test_send_log_to_connected_clients(websocket_manager, mock_websocket):
    """Test sending log messages to connected clients."""
    await websocket_manager.connect(mock_websocket, "test-project")
    
    # Send a log message
    await websocket_manager.send_log(
        "test-project", 
        "django", 
        "2024-01-01T10:00:00", 
        "Server started on port 8000"
    )
    
    # Verify WebSocket received the message
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]
    assert sent_message["type"] == "log"
    assert sent_message["server_name"] == "django"
    assert sent_message["line"] == "Server started on port 8000"


@pytest.mark.asyncio
async def test_send_status_update_to_connected_clients(websocket_manager, mock_websocket):
    """Test sending status updates to connected clients."""
    await websocket_manager.connect(mock_websocket, "test-project")
    
    # Send status update
    await websocket_manager.send_server_status(
        "test-project",
        "django",
        "running",
        pid=12345
    )
    
    # Verify WebSocket received the message
    mock_websocket.send_json.assert_called_once()
    sent_message = mock_websocket.send_json.call_args[0][0]
    assert sent_message["type"] == "status"
    assert sent_message["server_name"] == "django"
    assert sent_message["status"] == "running"
    assert sent_message["pid"] == 12345


@pytest.mark.asyncio
async def test_multiple_clients_receive_broadcasts(websocket_manager):
    """Test multiple connected clients all receive broadcasts."""
    # Create multiple mock websockets
    mock_ws1 = MagicMock(spec=WebSocket)
    mock_ws1.send_json = MagicMock(return_value=asyncio.Future())
    mock_ws1.send_json.return_value.set_result(None)
    
    mock_ws2 = MagicMock(spec=WebSocket)
    mock_ws2.send_json = MagicMock(return_value=asyncio.Future())
    mock_ws2.send_json.return_value.set_result(None)
    
    # Connect both to same project
    await websocket_manager.connect(mock_ws1, "test-project")
    await websocket_manager.connect(mock_ws2, "test-project")
    
    # Send a log message
    await websocket_manager.send_log(
        "test-project",
        "django",
        "2024-01-01T10:00:00",
        "Broadcast message"
    )
    
    # Both should receive the message
    mock_ws1.send_json.assert_called_once()
    mock_ws2.send_json.assert_called_once()


@pytest.mark.asyncio
async def test_disconnected_client_removed_on_send_error(websocket_manager, mock_websocket):
    """Test client is removed when send fails due to disconnection."""
    connection_id = await websocket_manager.connect(mock_websocket, "test-project")
    
    # Make send_json raise ConnectionError
    mock_websocket.send_json.side_effect = ConnectionError("Client disconnected")
    
    # Try to send a message
    await websocket_manager.send_log(
        "test-project",
        "django",
        "2024-01-01T10:00:00",
        "Test message"
    )
    
    # Client should be removed
    assert connection_id not in websocket_manager.active_connections


@pytest.mark.asyncio
async def test_broadcast_to_nonexistent_project(websocket_manager):
    """Test broadcasting to project with no connections works without error."""
    # Send to project with no connections
    await websocket_manager.send_log(
        "nonexistent-project",
        "django",
        "2024-01-01T10:00:00",
        "Test message"
    )
    
    # Should complete without error
    assert True  # If we get here, no exception was raised


@pytest.mark.asyncio
async def test_clients_isolated_by_project(websocket_manager):
    """Test clients only receive messages for their project."""
    # Create mock websockets for different projects
    mock_ws_project1 = MagicMock(spec=WebSocket)
    mock_ws_project1.send_json = MagicMock(return_value=asyncio.Future())
    mock_ws_project1.send_json.return_value.set_result(None)
    
    mock_ws_project2 = MagicMock(spec=WebSocket)
    mock_ws_project2.send_json = MagicMock(return_value=asyncio.Future())
    mock_ws_project2.send_json.return_value.set_result(None)
    
    # Connect to different projects
    await websocket_manager.connect(mock_ws_project1, "project1")
    await websocket_manager.connect(mock_ws_project2, "project2")
    
    # Send message to project1
    await websocket_manager.send_log(
        "project1",
        "django",
        "2024-01-01T10:00:00",
        "Project 1 message"
    )
    
    # Only project1 client should receive it
    mock_ws_project1.send_json.assert_called_once()
    mock_ws_project2.send_json.assert_not_called()