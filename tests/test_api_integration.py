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


def test_start_server_returns_ok_for_valid_project(test_app, auth_headers, test_project_config, project_directory):
    """Test POST /api/projects/{id}/servers/{name}/start/ returns 200 OK for a valid project."""
    # Update the mock file_ops to return the correct path for test-project
    test_app.app.state.deps.file_ops.get_safe_config_path.side_effect = lambda base, file: project_directory / file

    # Create config file in project directory
    config_file = project_directory / "devservers.yml"
    with open(config_file, "w") as f:
        yaml.dump(test_project_config, f)

    # Update project registry to have the correct path
    test_app.app.state.deps.project_registry._projects["test-project"]["path"] = str(project_directory)

    with patch("devserver_mcp.web_manager.process_manager.ProcessManager.start_process", return_value=True):
        response = test_app.post(
            "/api/projects/test-project/servers/django/start/",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"



def test_start_server_returns_404_for_unknown_project(test_app, auth_headers):
    """Test POST /api/projects/{id}/servers/{name}/start/ returns 404 for an unknown project."""
    response = test_app.post(
        "/api/projects/unknown-project/servers/django/start/",
        headers=auth_headers
    )
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_stop_server_returns_ok_for_valid_project(test_app, auth_headers):
    """Test POST /api/projects/{id}/servers/{name}/stop/ returns 200 OK for a valid project."""
    response = test_app.post(
        "/api/projects/test-project/servers/django/stop/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["stopped", "not_running"]


def test_get_server_status_returns_ok_for_valid_project(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/status/ returns 200 OK and server status."""
    response = test_app.get(
        "/api/projects/test-project/servers/django/status/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "pid" in data


def test_get_server_logs_returns_ok_for_valid_project(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/logs/ returns 200 OK and server logs."""
    response = test_app.get(
        "/api/projects/test-project/servers/django/logs/",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "lines" in data
    assert isinstance(data["lines"], list)


def test_get_server_logs_supports_pagination(test_app, auth_headers):
    """Test GET /api/projects/{id}/servers/{name}/logs/ supports pagination parameters."""
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


def test_register_project_returns_ok_for_valid_config(test_app, auth_headers, temp_home_dir):
    """Test POST /api/projects/ registers a new project with valid configuration."""
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


def test_register_project_rejects_invalid_path(test_app, auth_headers):
    """Test POST /api/projects/ rejects project registration with invalid paths."""
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




def test_full_server_lifecycle(test_app, auth_headers, test_project_config, project_directory):
    """Test the full lifecycle of a server: start, status, stop."""
    # Setup: Ensure config file exists and project is registered
    config_file = project_directory / "devservers.yml"
    with open(config_file, "w") as f:
        yaml.dump(test_project_config, f)
    test_app.app.state.deps.project_registry._projects["test-project"]["path"] = str(project_directory)
    test_app.app.state.deps.file_ops.get_safe_config_path.side_effect = lambda base, file: project_directory / file

    # 1. Start the server
    with patch("devserver_mcp.web_manager.process_manager.ProcessManager.start_process", return_value=True):
        start_response = test_app.post(
            "/api/projects/test-project/servers/django/start/",
            headers=auth_headers
        )
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "started"

    # 2. Check the server's status
    status_response = test_app.get(
        "/api/projects/test-project/servers/django/status/",
        headers=auth_headers
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] in ["running", "starting"]

    # 3. Stop the server
    with patch("devserver_mcp.web_manager.process_manager.ProcessManager.stop_process", return_value=True):
        stop_response = test_app.post(
            "/api/projects/test-project/servers/django/stop/",
            headers=auth_headers
        )
        assert stop_response.status_code == 200
        assert stop_response.json()["status"] == "stopped"


def test_api_rejects_invalid_authentication_token(test_app):
    """Test API endpoints reject requests with invalid bearer tokens."""
    invalid_headers = {"Authorization": "Bearer invalid-token"}
    
    response = test_app.get("/api/projects/", headers=invalid_headers)
    assert response.status_code == 401
    
    response = test_app.post(
        "/api/projects/test-project/servers/django/start/",
        headers=invalid_headers
    )
    assert response.status_code == 401


