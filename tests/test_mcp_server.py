from unittest.mock import MagicMock, patch

import httpx
import pytest

from devserver_mcp.mcp_server import get_server_logs, start_server, stop_server


@pytest.mark.asyncio
async def test_start_server_manager_not_running():
    """Test start_server tool when manager is not running."""
    with patch("devserver_mcp.mcp_server.discover_manager", return_value=(None, None)):
        
        result = await start_server("django", project_id="test-project")
        
        assert result.status == "error"
        assert "not running" in result.message


@pytest.mark.asyncio
async def test_start_server_with_project_id():
    """Test start_server tool with explicit project_id."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "started", "message": "Server started"}
    
    with patch("devserver_mcp.mcp_server.discover_manager", return_value=("http://localhost:7912", "test-token")), \
         patch("devserver_mcp.mcp_server.check_manager_health", return_value=True), \
         patch("httpx.AsyncClient.post", return_value=mock_response):
        
        result = await start_server("django", project_id="test-project")
        
        assert result.status == "started"
        assert result.message == "Server started"


@pytest.mark.asyncio
async def test_stop_server_success():
    """Test stop_server tool successfully stops server."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "stopped", "message": "Server stopped"}
    
    with patch("devserver_mcp.mcp_server.discover_manager", return_value=("http://localhost:7912", "test-token")), \
         patch("devserver_mcp.mcp_server.check_manager_health", return_value=True), \
         patch("httpx.AsyncClient.post", return_value=mock_response):
        
        result = await stop_server("django", project_id="test-project")
        
        assert result.status == "stopped"
        assert result.message == "Server stopped"


@pytest.mark.asyncio
async def test_get_server_logs_success():
    """Test get_server_logs tool returns logs successfully."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "status": "success",
        "lines": [
            {"timestamp": "2024-01-01T10:00:00", "message": "Server started", "source": "stdout"}
        ],
        "count": 1,
        "total": 10,
        "offset": 0,
        "has_more": True
    }
    
    with patch("devserver_mcp.mcp_server.discover_manager", return_value=("http://localhost:7912", "test-token")), \
         patch("devserver_mcp.mcp_server.check_manager_health", return_value=True), \
         patch("httpx.AsyncClient.get", return_value=mock_response):
        
        result = await get_server_logs("django", project_id="test-project", offset=0, limit=100)
        
        assert result.status == "success"
        assert len(result.lines) == 1
        assert result.lines[0].message == "Server started"
        assert result.has_more is True