import asyncio
from unittest.mock import MagicMock, patch

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
    with patch.object(ManagedProcess, "stop", return_value=None) as mock_stop:
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


def test_shutdown_all(manager):
    proc = manager.processes["api"]
    proc.process = MagicMock()
    proc.process.returncode = None
    with patch.object(ManagedProcess, "stop", return_value=None) as mock_stop:
        manager.shutdown_all()
        mock_stop.assert_called()


def test_devservermcp_config_injection(simple_config):
    mcp = DevServerMCP(config=simple_config)
    assert isinstance(mcp.manager, DevServerManager)
    assert mcp.config is simple_config
