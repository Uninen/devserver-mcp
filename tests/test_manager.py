import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp import DevServerMCP
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
    proc.process.returncode = None  # indicates running process
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


def test_get_server_status_running(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.start_time = 1234567890
    status = manager.get_server_status("api")
    assert status["status"] == "running"
    assert status["type"] == "managed"


def test_get_server_status_external(manager):
    with patch.object(DevServerManager, "_is_port_in_use", return_value=True):
        proc = manager.processes["api"]
        proc.process = None
        status = manager.get_server_status("api")
        assert status["status"] == "running"
        assert status["type"] == "external"


def test_get_server_status_not_found(manager):
    status = manager.get_server_status("notfound")
    assert status["status"] == "error"
    assert "not found" in status["message"]


def test_get_server_logs_success(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    proc.logs.extend(["line1", "line2"])
    logs = manager.get_server_logs("api", lines=2)
    assert logs["status"] == "success"
    assert logs["lines"] == ["line1", "line2"]

    logs = manager.get_server_logs("foo", lines=2)
    assert logs["status"] == "error"
    assert "not found" in logs["message"]


def test_get_server_logs_not_running(manager):
    with patch.object(DevServerManager, "_is_port_in_use", return_value=False):
        logs = manager.get_server_logs("api")
        assert logs["status"] == "error"
        assert "not running" in logs["message"]


def test_get_server_logs_external(manager):
    with patch.object(DevServerManager, "_is_port_in_use", return_value=True):
        logs = manager.get_server_logs("api")
        assert logs["status"] == "error"
        assert "external" in logs["message"].lower()


def test_get_all_servers(manager):
    servers = manager.get_all_servers()
    assert isinstance(servers, list)
    assert any(s["name"] == "api" for s in servers)


@pytest.mark.asyncio
async def test_shutdown_all(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    with patch.object(ManagedProcess, "stop", return_value=asyncio.Future()) as mock_stop:
        mock_stop.return_value.set_result(None)
        await manager.shutdown_all()
        mock_stop.assert_called()


def test_devservermcp_config_injection(simple_config):
    mcp = DevServerMCP(config=simple_config)
    assert isinstance(mcp.manager, DevServerManager)
    assert mcp.config is simple_config


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
            if server_name == "no_autostart_web":  # Has autostart=False
                return {"status": "stopped"}
            # Should not be called for other servers in this config
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}  # Keep linters happy

        mock_get_status.side_effect = get_status_side_effect
        # Mock the return value of the actual start_server, not the one in this test
        mock_start_server.return_value = {"status": "started", "message": "Server started"}

        await manager.autostart_configured_servers()

        # Assert start_server was called for 'autostart_api'
        mock_start_server.assert_called_once_with("autostart_api")
        # Ensure get_server_status was called only for 'autostart_api'
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_server_not_started_if_autostart_true_but_external(autostart_manager):
    manager = autostart_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):

        def get_status_side_effect(server_name):
            if server_name == "autostart_api":  # This one has autostart=True
                return {"status": "running", "type": "external"}  # Simulate external process
            if server_name == "no_autostart_web":
                return {"status": "stopped"}
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}

        mock_get_status.side_effect = get_status_side_effect

        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        # Ensure get_server_status was called only for 'autostart_api'
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_server_not_started_if_autostart_true_but_managed_running(autostart_manager):
    manager = autostart_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):

        def get_status_side_effect(server_name):
            if server_name == "autostart_api":  # This one has autostart=True
                return {"status": "running", "type": "managed"}  # Simulate managed process already running
            if server_name == "no_autostart_web":
                return {"status": "stopped"}
            pytest.fail(f"Unexpected call to get_server_status with {server_name}")
            return {}

        mock_get_status.side_effect = get_status_side_effect

        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        # Ensure get_server_status was called only for 'autostart_api'
        mock_get_status.assert_called_once_with("autostart_api")


@pytest.mark.asyncio
async def test_autostart_servers_not_started_if_all_autostart_false(all_autostart_false_manager):
    manager = all_autostart_false_manager
    with (
        patch.object(manager, "get_server_status", new_callable=MagicMock) as mock_get_status,
        patch.object(manager, "start_server", new_callable=AsyncMock) as mock_start_server,
    ):
        # mock_get_status.return_value is not needed as get_server_status should not be called.

        await manager.autostart_configured_servers()

        mock_start_server.assert_not_called()
        # get_server_status should not be called as no server has autostart=True
        mock_get_status.assert_not_called()
