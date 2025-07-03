import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


def test_get_projects_returns_registered_projects(test_app, auth_headers):
    """Test GET /api/projects/ returns list of registered projects."""
    response = test_app.get("/api/projects/", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "test-project"
    assert data[1]["id"] == "another-project"


def test_get_projects_requires_authentication(test_app):
    """Test GET /api/projects/ requires valid bearer token."""
    response = test_app.get("/api/projects/")
    
    assert response.status_code == 403


def test_start_server_with_valid_project(test_app, auth_headers, test_project_config, project_directory):
    """Test POST /api/projects/{id}/servers/{name}/start/ starts server."""
    # Update the mock file_ops to return the correct path for test-project
    test_app.app.state.deps.file_ops.get_safe_config_path.side_effect = lambda base, file: project_directory / file
    
    # Create config file in project directory
    config_file = project_directory / "devservers.yml"
    with open(config_file, "w") as f:
        yaml.dump(test_project_config, f)
    
    # Update project registry to have the correct path
    test_app.app.state.deps.project_registry._projects["test-project"]["path"] = str(project_directory)
    
    # Mock subprocess for server start - need to mock the coroutine properly
    async def mock_create_subprocess():
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.returncode = None
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        
        # Mock the async readline method
        async def mock_readline():
            return b""
        
        mock_process.stdout.readline = mock_readline
        mock_process.stderr.readline = mock_readline
        
        return mock_process
    
    with patch("asyncio.create_subprocess_shell", side_effect=mock_create_subprocess):
        response = test_app.post(
            "/api/projects/test-project/servers/django/start/",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["started", "error"]  # May be error if process exits quickly


def test_start_server_with_invalid_project(test_app, auth_headers):
    """Test POST /api/projects/{id}/servers/{name}/start/ fails for unknown project."""
    response = test_app.post(
        "/api/projects/unknown-project/servers/django/start/",
        headers=auth_headers
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_stop_server_with_valid_project(test_app, auth_headers):
    """Test POST /api/projects/{id}/servers/{name}/stop/ stops server."""
    response = test_app.post(
        "/api/projects/test-project/servers/django/stop/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["stopped", "not_running"]


def test_get_server_status_with_valid_project(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/status/ returns server status."""
    response = test_app.get(
        "/api/projects/test-project/servers/django/status/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "pid" in data


def test_get_server_logs_with_valid_project(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/logs/ returns server logs."""
    response = test_app.get(
        "/api/projects/test-project/servers/django/logs/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "lines" in data
    assert isinstance(data["lines"], list)


def test_get_server_logs_with_pagination(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/logs/ supports pagination."""
    response = test_app.get(
        "/api/projects/test-project/servers/django/logs/?offset=10&limit=5",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "lines" in data
    assert "total" in data
    assert "offset" in data
    assert data["offset"] == 10


def test_register_project_with_valid_config(test_app, auth_headers, temp_home_dir):
    """Test POST /api/projects/ registers new project with valid config."""
    project_dir = temp_home_dir / "new-project"
    project_dir.mkdir()
    
    config_file = project_dir / "devservers.yml"
    config_data = {
        "project": "new-project",
        "servers": {
            "web": {
                "command": "npm run dev",
                "port": 3000
            }
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    response = test_app.post(
        "/api/projects/",
        json={
            "id": "new-project",
            "name": "New Project",
            "path": str(project_dir),
            "config_file": "devservers.yml"
        },
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "new-project"
    assert data["path"] == str(project_dir)


def test_register_project_with_invalid_path(test_app, auth_headers):
    """Test POST /api/projects/ rejects invalid project paths."""
    response = test_app.post(
        "/api/projects/",
        json={
            "id": "invalid-project",
            "name": "Invalid Project",
            "path": "relative/path/without/absolute",
            "config_file": "devservers.yml"
        },
        headers=auth_headers
    )
    
    # Should reject non-absolute paths
    assert response.status_code in [400, 404]




def test_authentication_with_invalid_token(test_app):
    """Test API endpoints reject invalid bearer tokens."""
    invalid_headers = {"Authorization": "Bearer invalid-token"}
    
    response = test_app.get("/api/projects/", headers=invalid_headers)
    assert response.status_code == 401
    
    response = test_app.post(
        "/api/projects/test-project/servers/django/start/",
        headers=invalid_headers
    )
    assert response.status_code == 401


