import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def simple_config():
    return Config(
        servers={
            "api": ServerConfig(command="echo hello", working_dir=".", port=12345),
            "web": ServerConfig(command="echo world", working_dir=".", port=12346),
        }
    )


@pytest.fixture
def temp_state_dir():
    with tempfile.TemporaryDirectory() as tmpdir, patch.object(Path, "home", return_value=Path(tmpdir)):
        yield tmpdir


@pytest.fixture
def manager(simple_config, temp_state_dir):
    return DevServerManager(simple_config, "/test/project")


@pytest.mark.asyncio
async def test_start_server_success(manager):
    # Mock subprocess creation (system boundary)
    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.sleep"):
            result = await manager.start_server("api")

    assert result["status"] == "started"
    assert "started" in result["message"]
    mock_create_subprocess.assert_called_once()


@pytest.mark.asyncio
async def test_start_server_port_in_use(manager):
    # Mock port checking (system boundary - socket)
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value = mock_socket

        result = await manager.start_server("api")

    assert result["status"] == "error"
    assert "in use" in result["message"]


@pytest.mark.asyncio
async def test_start_server_not_found(manager):
    result = await manager.start_server("notfound")
    assert result["status"] == "error"
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_start_server_already_running(manager):
    # First start the server
    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.sleep"), patch("os.kill", return_value=None):
            await manager.start_server("api")

            # Now try to start it again
            result = await manager.start_server("api")

    assert result["status"] == "already_running"
    assert "already running" in result["message"]


@pytest.mark.asyncio
async def test_stop_server_success(manager):
    # First start the server
    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.wait.return_value = None
        mock_process.terminate = MagicMock()
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.sleep"), patch("os.kill", return_value=None):
            await manager.start_server("api")

            # Now stop it
            with (
                patch("os.killpg")
                if not hasattr(asyncio, "WindowsProactorEventLoopPolicy")
                else patch.object(mock_process, "terminate")
            ):
                result = await manager.stop_server("api")

    assert result["status"] == "stopped"
    assert "stopped" in result["message"]


@pytest.mark.asyncio
async def test_stop_server_external(manager):
    # Mock port in use but process not managed
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value = mock_socket

        result = await manager.stop_server("api")

    assert result["status"] == "error"
    assert "external" in result["message"]


@pytest.mark.asyncio
async def test_stop_server_not_found(manager):
    result = await manager.stop_server("notfound")
    assert result["status"] == "error"
    assert "not found" in result["message"]


@pytest.mark.asyncio
async def test_stop_server_not_running(manager):
    # Mock port not in use
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.return_value = None  # Port is free
        mock_socket_class.return_value = mock_socket

        result = await manager.stop_server("api")

    assert result["status"] == "not_running"
    assert "not running" in result["message"]


@pytest.fixture
def autostart_config():
    return Config(
        servers={
            "autostart_api": ServerConfig(command="echo autostart", working_dir=".", port=12347, autostart=True),
            "no_autostart_web": ServerConfig(command="echo no_autostart", working_dir=".", port=12348, autostart=False),
        }
    )


@pytest.mark.asyncio
async def test_autostart_configured_servers(autostart_config, temp_state_dir):
    manager = DevServerManager(autostart_config, "/test/project")

    # Mock subprocess creation for autostart server
    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.sleep"):
            await manager.autostart_configured_servers()

    # Should have started only the autostart server
    assert mock_create_subprocess.call_count == 1


def test_is_port_in_use_free_port(manager):
    # Mock socket bind success (port is free)
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.return_value = None
        mock_socket_class.return_value = mock_socket

        result = manager._is_port_in_use(65535)

    assert result is False


def test_is_port_in_use_used_port(manager):
    # Mock socket bind failure (port is in use)
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value = mock_socket

        result = manager._is_port_in_use(12345)

    assert result is True


def test_get_server_status_running(manager):
    # Start server first
    api_process = manager.processes["api"]
    api_process.pid = 12345
    api_process.start_time = 123456789.0

    with patch("os.kill", return_value=None):  # Process is alive
        status = manager.get_server_status("api")

    assert status["status"] == "running"
    assert status["port"] == 12345


def test_get_server_status_external(manager):
    # Server not running but port in use
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value = mock_socket

        status = manager.get_server_status("api")

    assert status["status"] == "external"
    assert status["port"] == 12345


def test_get_server_status_stopped(manager):
    # Server not running and port free
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.return_value = None
        mock_socket_class.return_value = mock_socket

        api_process = manager.processes["api"]
        api_process.error = "Test error"

        status = manager.get_server_status("api")

    assert status["status"] == "stopped"
    assert status["error"] == "Test error"


def test_get_server_logs_not_found(manager):
    result = manager.get_server_logs("notfound")
    assert result["status"] == "error"
    assert "not found" in result["message"]


def test_get_server_logs_not_running(manager):
    # Server not running and port free
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.return_value = None
        mock_socket_class.return_value = mock_socket

        result = manager.get_server_logs("api")

    assert result["status"] == "error"
    assert "not running" in result["message"]


def test_get_server_logs_external_process(manager):
    # Port in use but not our process
    with patch("socket.socket") as mock_socket_class:
        mock_socket = MagicMock()
        mock_socket.__enter__.return_value = mock_socket
        mock_socket.bind.side_effect = OSError("Port in use")
        mock_socket_class.return_value = mock_socket

        result = manager.get_server_logs("api")

    assert result["status"] == "error"
    assert "external process" in result["message"]


def test_get_server_logs_success(manager):
    # Simulate running process with logs
    api_process = manager.processes["api"]
    api_process.pid = 12345
    api_process.logs = ["line1", "line2", "line3"]

    with patch("os.kill", return_value=None):  # Process is alive
        result = manager.get_server_logs("api", lines=2)

    assert result["status"] == "success"
    assert result["lines"] == ["line2", "line3"]
    assert result["count"] == 2


def test_get_all_servers(manager):
    # Set up mixed states
    api_process = manager.processes["api"]
    api_process.error = "Test error"

    web_process = manager.processes["web"]
    web_process.pid = 12346

    with patch("os.kill") as mock_kill:
        # api: dead process
        # web: alive process
        def kill_side_effect(pid, sig):
            if pid == 12346:
                return None  # web is alive
            raise ProcessLookupError()  # api is dead

        mock_kill.side_effect = kill_side_effect

        with patch("socket.socket") as mock_socket_class:
            mock_socket = MagicMock()
            mock_socket.__enter__.return_value = mock_socket
            mock_socket.bind.return_value = None  # Ports are free
            mock_socket_class.return_value = mock_socket

            servers = manager.get_all_servers()

    assert len(servers) == 2

    api_server = next(s for s in servers if s["name"] == "api")
    assert api_server["status"] == "stopped"
    assert api_server["port"] == 12345
    assert api_server["error"] == "Test error"

    web_server = next(s for s in servers if s["name"] == "web")
    assert web_server["status"] == "running"
    assert web_server["port"] == 12346


@pytest.mark.asyncio
async def test_shutdown_all(manager):
    # Start both servers
    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        for name in ["api", "web"]:
            mock_process = AsyncMock()
            mock_process.returncode = None
            mock_process.pid = 12345 if name == "api" else 12346
            mock_process.stdout = AsyncMock()
            mock_process.stdout.readline.return_value = b""
            mock_process.wait.return_value = None
            mock_process.terminate = MagicMock()
            mock_create_subprocess.return_value = mock_process

            with patch("asyncio.sleep"), patch("os.kill", return_value=None):
                await manager.start_server(name)

    # Now shutdown all - need to mock os.kill for process checking
    with (
        patch("os.killpg") if sys.platform != "win32" else patch("asyncio.sleep"),
        patch("os.kill", return_value=None),
        patch("asyncio.sleep"),
    ):
        await manager.shutdown_all()

    # Check all processes are stopped
    for process in manager.processes.values():
        assert process.pid is None


def test_log_callback_registration(manager):
    callback = MagicMock()
    manager.add_log_callback(callback)
    assert callback in manager._log_callbacks


def test_status_callback_registration(manager):
    callback = MagicMock()
    manager.add_status_callback(callback)
    assert callback in manager._status_callbacks


@pytest.mark.asyncio
async def test_notify_log_sync_callback(manager):
    callback = MagicMock()
    manager.add_log_callback(callback)

    await manager._notify_log("server", "timestamp", "message")

    callback.assert_called_once_with("server", "timestamp", "message")


@pytest.mark.asyncio
async def test_notify_log_async_callback(manager):
    callback = AsyncMock()
    manager.add_log_callback(callback)

    await manager._notify_log("server", "timestamp", "message")

    callback.assert_called_once_with("server", "timestamp", "message")


def test_notify_status_change(manager):
    callback = MagicMock()
    manager.add_status_callback(callback)

    manager._notify_status_change()

    callback.assert_called_once()
