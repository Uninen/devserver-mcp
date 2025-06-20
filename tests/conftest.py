import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from devserver_mcp.state import StateManager
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def long_running_command():
    """Command that runs until killed."""
    return "tail -f /dev/null"


@pytest.fixture
def echo_command():
    """Command that exits immediately after output."""
    return "echo 'test output'"


@pytest.fixture
def simple_server_config(echo_command):
    """Basic server configuration with a command that exits quickly."""
    return ServerConfig(command=echo_command, working_dir=".", port=12345)


@pytest.fixture
def echo_server_config(echo_command):
    """Server configuration with an echo command that exits immediately."""
    return ServerConfig(command=echo_command, working_dir=".", port=12345)


@pytest.fixture
def running_server_config(long_running_command):
    """Server configuration with a long-running command for tests that need running servers."""
    return ServerConfig(command=long_running_command, working_dir=".", port=12345)


@pytest.fixture
def simple_config(simple_server_config):
    """Basic configuration with one server."""
    return Config(servers={"api": simple_server_config})


@pytest.fixture
def multi_server_config(echo_command):
    """Configuration with multiple servers."""
    return Config(
        servers={
            "api": ServerConfig(command=echo_command, working_dir=".", port=12345),
            "web": ServerConfig(command=echo_command, working_dir=".", port=12346),
        }
    )


@pytest.fixture
def running_multi_server_config(long_running_command):
    """Configuration with multiple servers that stay running."""
    return Config(
        servers={
            "api": ServerConfig(command=long_running_command, working_dir=".", port=12345),
            "web": ServerConfig(command=long_running_command, working_dir=".", port=12346),
        }
    )


@pytest.fixture
def autostart_config(long_running_command):
    """Configuration with autostart and manual servers."""
    return Config(
        servers={
            "autostart": ServerConfig(command=long_running_command, working_dir=".", port=12349, autostart=True),
            "manual": ServerConfig(command=long_running_command, working_dir=".", port=12350, autostart=False),
        }
    )


@pytest.fixture
def running_config(long_running_command):
    """Configuration with one server that stays running."""
    return Config(servers={"api": ServerConfig(command=long_running_command, working_dir=".", port=12345)})


@pytest.fixture
def temp_state_dir():
    """Temporary directory for state files with mocked home directory."""
    with tempfile.TemporaryDirectory() as tmpdir, patch.object(Path, "home", return_value=Path(tmpdir)):
        yield tmpdir


@pytest.fixture
def temp_state_manager():
    """State manager with temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_home = Path.home
        with patch.object(Path, "home", return_value=Path(tmpdir)):
            yield StateManager("/test/project")
        Path.home = original_home
