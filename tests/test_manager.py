import asyncio

import pytest

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import OperationStatus, ServerStatusEnum


@pytest.fixture
def manager(multi_server_config, temp_state_dir):
    return DevServerManager(multi_server_config, "/test/project")


@pytest.fixture
def running_manager(running_multi_server_config, temp_state_dir):
    return DevServerManager(running_multi_server_config, "/test/project")


@pytest.mark.asyncio
async def test_start_server_success(running_manager):
    result = await running_manager.start_server("api")

    assert result.status == OperationStatus.STARTED
    assert "started" in result.message

    status = running_manager.get_server_status("api")
    assert status["status"] == "running"

    await running_manager.stop_server("api")


@pytest.mark.asyncio
async def test_start_server_not_found(manager):
    result = await manager.start_server("notfound")

    assert result.status == OperationStatus.ERROR
    assert "not found" in result.message


@pytest.mark.asyncio
async def test_start_server_already_running(running_manager):
    result1 = await running_manager.start_server("api")
    assert result1.status == OperationStatus.STARTED

    result2 = await running_manager.start_server("api")
    assert result2.status == OperationStatus.ALREADY_RUNNING
    assert "already running" in result2.message

    await running_manager.stop_server("api")


@pytest.mark.asyncio
async def test_stop_server_success(running_manager):
    await running_manager.start_server("api")

    result = await running_manager.stop_server("api")
    assert result.status == OperationStatus.STOPPED
    assert "stopped" in result.message

    status = running_manager.get_server_status("api")
    assert status["status"] == "stopped"


@pytest.mark.asyncio
async def test_stop_server_not_running(manager):
    result = await manager.stop_server("api")

    assert result.status == OperationStatus.NOT_RUNNING
    assert "not running" in result.message


@pytest.mark.asyncio
async def test_stop_server_not_found(manager):
    result = await manager.stop_server("notfound")

    assert result.status == OperationStatus.ERROR
    assert "not found" in result.message


def test_get_server_status_stopped(manager):
    status = manager.get_server_status("api")

    assert status["status"] == "stopped"
    assert status["port"] == 12345
    assert status.get("error") is None


def test_get_devserver_logs_not_found(manager):
    result = manager.get_devserver_logs("notfound")

    assert result.status == "error"
    assert "not found" in result.message


def test_get_devserver_logs_not_running(manager):
    result = manager.get_devserver_logs("api")

    assert result.status == "error"
    assert "not running" in result.message


@pytest.mark.asyncio
async def test_get_devserver_logs_success(running_manager):
    await running_manager.start_server("api")
    await asyncio.sleep(0.1)

    result = running_manager.get_devserver_logs("api", limit=10)

    assert result.status == "success"
    assert result.lines is not None
    assert isinstance(result.lines, list)
    assert result.count is not None
    assert result.total is not None

    await running_manager.stop_server("api")


def test_get_devserver_statuses(manager):
    servers = manager.get_devserver_statuses()

    assert len(servers) == 2

    api_server = next(s for s in servers if s.name == "api")
    assert api_server.status == ServerStatusEnum.STOPPED
    assert api_server.port == 12345

    web_server = next(s for s in servers if s.name == "web")
    assert web_server.status == ServerStatusEnum.STOPPED
    assert web_server.port == 12346


@pytest.mark.asyncio
async def test_shutdown_all(running_manager):
    await running_manager.start_server("api")
    await running_manager.start_server("web")

    assert running_manager.get_server_status("api")["status"] == "running"
    assert running_manager.get_server_status("web")["status"] == "running"

    await running_manager.shutdown_all()

    assert running_manager.get_server_status("api")["status"] == "stopped"
    assert running_manager.get_server_status("web")["status"] == "stopped"


@pytest.mark.asyncio
async def test_autostart_configured_servers(autostart_config, temp_state_dir):
    manager = DevServerManager(autostart_config, "/test/project")

    await manager.autostart_configured_servers()
    await asyncio.sleep(0.2)

    assert manager.get_server_status("autostart")["status"] == "running"
    assert manager.get_server_status("manual")["status"] == "stopped"

    await manager.shutdown_all()
