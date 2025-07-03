import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.web_manager.app import create_app
from devserver_mcp.web_manager.config import ManagerConfig
from devserver_mcp.web_manager.registry import ProjectRegistry


@pytest.fixture
def long_running_command():
    return "tail -f /dev/null"


@pytest.fixture
def echo_command():
    return "echo 'test output'"


@pytest.fixture
def simple_server_config(echo_command):
    return ServerConfig(command=echo_command, working_dir=".", port=12345)


@pytest.fixture
def simple_config(simple_server_config):
    return Config(servers={"api": simple_server_config})




@pytest.fixture
def temp_home_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(Path, "home", return_value=Path(tmpdir)):
            yield Path(tmpdir)




@pytest.fixture
def real_process_manager():
    """Real process manager for testing."""
    from devserver_mcp.web_manager.process_manager import ProcessManager
    return ProcessManager()


@pytest.fixture
def real_websocket_manager():
    """Real WebSocket manager for testing."""
    from devserver_mcp.web_manager.websocket_manager import WebSocketManager
    return WebSocketManager()


@pytest.fixture
def mock_file_ops(test_manager_config):
    """Mock file operations for testing."""
    from devserver_mcp.web_manager.file_ops import FileOperations
    
    file_ops = MagicMock(spec=FileOperations)
    file_ops.load_config_file.return_value = {
        "projects": {
            "test-project": {
                "id": "test-project",
                "name": "Test Project",
                "path": "/tmp/test-project",
                "config_file": "devservers.yml"
            },
            "another-project": {
                "id": "another-project",
                "name": "Another Project",
                "path": "/tmp/another-project",
                "config_file": "devservers.yml"
            }
        }
    }
    file_ops.save_config_file.return_value = None
    file_ops.write_status_file.return_value = None
    file_ops.validate_project_path.side_effect = lambda path: Path(path)
    file_ops.get_safe_config_path.side_effect = lambda base, file: Path(base) / file
    return file_ops


@pytest.fixture
def test_project_registry(mock_file_ops):
    """Pre-configured project registry for testing."""
    registry = ProjectRegistry(mock_file_ops)
    return registry


@pytest.fixture
def test_manager_config(temp_home_dir):
    """Test manager configuration."""
    return ManagerConfig(
        config_dir=temp_home_dir / ".devserver-mcp"
    )


@pytest.fixture
def test_app(test_manager_config, real_process_manager, real_websocket_manager, test_project_registry, mock_file_ops):
    """FastAPI test app with real components and mocked system boundaries."""
    from devserver_mcp.web_manager.dependencies import Dependencies
    
    # Create dependencies with real components but mocked system boundaries
    deps = Dependencies(
        config=test_manager_config,
        file_ops=mock_file_ops,
        project_registry=test_project_registry,
        process_manager=real_process_manager,
        websocket_manager=None,  # Will be set by lifespan
        bearer_token="test-token-123"
    )
    
    # Create a fresh app instance with our dependencies
    app = create_app(deps)
    
    # Use the with statement to handle lifespan events
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_project_config():
    """Sample project configuration for testing."""
    return {
        "project": "test-project",
        "servers": {
            "django": {
                "command": "python manage.py runserver",
                "port": 8000,
                "autostart": True
            },
            "celery": {
                "command": "celery -A myproject worker",
                "port": 8001,
                "autostart": False
            }
        }
    }


@pytest.fixture
def auth_headers():
    """Authorization headers for API testing."""
    return {"Authorization": "Bearer test-token-123"}


@pytest.fixture
def project_directory(temp_home_dir):
    """Create a temporary project directory with config file."""
    project_path = temp_home_dir / "test-project"
    project_path.mkdir(parents=True)
    return project_path