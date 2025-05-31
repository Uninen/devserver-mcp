import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.process import ManagedProcess
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
def manager(simple_config):
    return DevServerManager(simple_config)


@pytest.mark.asyncio
async def test_start_server_success(manager):
    with patch.object(ManagedProcess, "start", return_value=asyncio.Future()) as mock_start:
        mock_start.return_value.set_result(True)
        with patch.object(DevServerManager, "_is_port_in_use", return_value=False):
            result = await manager.start_server("api")
            assert result["status"] == "started"
            assert "started" in result["message"]


@pytest.mark.asyncio
async def test_start_server_port_in_use(manager):
    with patch.object(DevServerManager, "_is_port_in_use", return_value=True):
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
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.process.pid = 123

    result = await manager.start_server("api")
    assert result["status"] == "already_running"
    assert "already running" in result["message"]


@pytest.mark.asyncio
async def test_stop_server_success(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.process.pid = 123
    with patch.object(ManagedProcess, "stop", return_value=asyncio.Future()) as mock_stop:
        mock_stop.return_value.set_result(None)
        result = await manager.stop_server("api")
        assert result["status"] == "stopped"
        assert "stopped" in result["message"]
        mock_stop.assert_called_once()


@pytest.mark.asyncio
async def test_stop_server_external(manager):
    with patch.object(DevServerManager, "_is_port_in_use", return_value=True):
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
    with patch.object(DevServerManager, "_is_port_in_use", return_value=False):
        result = await manager.stop_server("api")
        assert result["status"] == "not_running"
        assert "not running" in result["message"]


@pytest.fixture
def autostart_true_config():
    return Config(
        servers={
            "autostart_api": ServerConfig(command="echo autostart_api", working_dir=".", port=12347, autostart=True),
            "no_autostart_web": ServerConfig(
                command="echo no_autostart_web", working_dir=".", port=12348, autostart=False
            ),
        }
    )


@pytest.fixture
def autostart_manager(autostart_true_config):
    return DevServerManager(autostart_true_config)


@pytest.fixture
def all_autostart_false_config():
    return Config(
        servers={
            "server_one": ServerConfig(command="echo one", working_dir=".", port=12351, autostart=False),
            "server_two": ServerConfig(command="echo two", working_dir=".", port=12352, autostart=False),
        }
    )


@pytest.fixture
def all_autostart_false_manager(all_autostart_false_config):
    return DevServerManager(all_autostart_false_config)


@pytest.mark.asyncio
async def test_autostart_server_starts_when_autostart_true_and_stopped(autostart_manager):
    manager = autostart_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):

        def get_status_side_effect(server_name):
            if server_name == "autostart_api":
                return {"status": "stopped"}
            if server_name == "no_autostart_web":
                return {"status": "stopped"}
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}

        mock_get_status.side_effect = get_status_side_effect
        mock_start_server.return_value = {"status": "started", "message": "Server started"}

        await manager.autostart_configured_servers()

        mock_start_server.assert_called_once_with("autostart_api")
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_server_not_started_if_autostart_true_but_external(autostart_manager):
    manager = autostart_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):

        def get_status_side_effect(server_name):
            if server_name == "autostart_api":
                return {"status": "running", "type": "external"}
            if server_name == "no_autostart_web":
                return {"status": "stopped"}
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}

        mock_get_status.side_effect = get_status_side_effect

        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_server_not_started_if_autostart_true_but_managed_running(autostart_manager):
    manager = autostart_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):

        def get_status_side_effect(server_name):
            if server_name == "autostart_api":
                return {"status": "running", "type": "managed"}
            if server_name == "no_autostart_web":
                return {"status": "stopped"}
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}

        mock_get_status.side_effect = get_status_side_effect

        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_servers_not_started_if_all_autostart_false(all_autostart_false_manager):
    manager = all_autostart_false_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):
        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        mock_get_status.assert_not_called()


def test_is_port_in_use_free_port(manager):
    result = manager._is_port_in_use(65535)
    assert result is False


def test_is_port_in_use_used_port(manager):
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("localhost", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        result = manager._is_port_in_use(port)
        assert result is True
    finally:
        sock.close()


def test_get_server_status_running_managed(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.process.pid = 123

    status = manager.get_server_status("api")
    assert status["status"] == "running"
    assert status["type"] == "managed"
    assert status["port"] == 12345


def test_get_server_status_running_external(manager):
    with patch.object(manager, "_is_port_in_use", return_value=True):
        status = manager.get_server_status("api")
        assert status["status"] == "running"
        assert status["type"] == "external"
        assert status["port"] == 12345


def test_get_server_status_stopped(manager):
    proc = manager.processes["api"]
    proc.error = "Test error"

    with patch.object(manager, "_is_port_in_use", return_value=False):
        status = manager.get_server_status("api")
        assert status["status"] == "stopped"
        assert status["type"] == "none"
        assert status["error"] == "Test error"


def test_get_server_logs_not_found(manager):
    result = manager.get_server_logs("notfound")
    assert result["status"] == "error"
    assert "not found" in result["message"]


def test_get_server_logs_not_running(manager):
    with patch.object(manager, "_is_port_in_use", return_value=False):
        result = manager.get_server_logs("api")
        assert result["status"] == "error"
        assert "not running" in result["message"]


def test_get_server_logs_external_process(manager):
    with patch.object(manager, "_is_port_in_use", return_value=True):
        result = manager.get_server_logs("api")
        assert result["status"] == "error"
        assert "external process" in result["message"]


def test_get_server_logs_success(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.logs.extend(["line1", "line2", "line3"])

    result = manager.get_server_logs("api", lines=2)
    assert result["status"] == "success"
    assert result["lines"] == ["line2", "line3"]
    assert result["count"] == 2


def test_get_all_servers(manager):
    proc = manager.processes["api"]
    proc.error = "Test error"

    with patch.object(manager, "_is_port_in_use", return_value=False):
        servers = manager.get_all_servers()
        assert len(servers) == 2

        api_server = next(s for s in servers if s["name"] == "api")
        assert api_server["status"] == "error"
        assert api_server["port"] == 12345
        assert api_server["error"] == "Test error"
        assert api_server["external_running"] is False


@pytest.mark.asyncio
async def test_shutdown_all(manager):
    proc1 = manager.processes["api"]
    proc2 = manager.processes["web"]

    proc1.process = MagicMock()
    proc1.process.returncode = None
    proc2.process = MagicMock()
    proc2.process.returncode = None

    with patch.object(ManagedProcess, "stop", return_value=asyncio.Future()) as mock_stop:
        mock_stop.return_value.set_result(None)

        await manager.shutdown_all()

        assert mock_stop.call_count == 2


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
