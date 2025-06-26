import asyncio
from unittest.mock import patch

import pytest

from devserver_mcp.manager import DevServerManager


@pytest.fixture
def manager_with_logs(multi_server_config, temp_state_dir):
    manager = DevServerManager(multi_server_config, "/test/project")

    process = manager.processes["api"]
    for i in range(150):
        process.logs.append(f"Test log line {i}")

    # Mock the process as running
    with patch.object(process, "_is_process_alive", return_value=True):
        process.pid = 12345
        process.start_time = 1234567890
        yield manager
        return

    return manager


@pytest.mark.asyncio
async def test_get_devserver_logs_default_pagination(manager_with_logs):
    result = manager_with_logs.get_devserver_logs("api")

    assert result.status == "success"
    assert result.count == 100
    assert result.total == 150
    assert result.offset == 0
    assert result.has_more is True
    assert result.lines[0] == "Test log line 149"
    assert result.lines[99] == "Test log line 50"


@pytest.mark.asyncio
async def test_get_devserver_logs_custom_limit(manager_with_logs):
    result = manager_with_logs.get_devserver_logs("api", offset=0, limit=20)

    assert result.status == "success"
    assert result.count == 20
    assert result.total == 150
    assert result.has_more is True
    assert len(result.lines) == 20


@pytest.mark.asyncio
async def test_get_devserver_logs_with_offset(manager_with_logs):
    result = manager_with_logs.get_devserver_logs("api", offset=50, limit=20)

    assert result.status == "success"
    assert result.count == 20
    assert result.offset == 50
    assert result.lines[0] == "Test log line 99"
    assert result.lines[19] == "Test log line 80"


@pytest.mark.asyncio
async def test_get_devserver_logs_forward_order(manager_with_logs):
    result = manager_with_logs.get_devserver_logs("api", offset=0, limit=10, reverse=False)

    assert result.status == "success"
    assert result.count == 10
    assert result.lines[0] == "Test log line 0"
    assert result.lines[9] == "Test log line 9"


@pytest.mark.asyncio
async def test_get_devserver_logs_negative_offset(manager_with_logs):
    # -20 becomes offset 130 (150-20), so we get 10 items before position 130
    result = manager_with_logs.get_devserver_logs("api", offset=-20, limit=10)

    assert result.status == "success"
    assert result.count == 10
    assert result.lines[0] == "Test log line 19"
    assert result.lines[9] == "Test log line 10"


@pytest.mark.asyncio
async def test_get_devserver_logs_beyond_total(manager_with_logs):
    result = manager_with_logs.get_devserver_logs("api", offset=200, limit=10)

    assert result.status == "success"
    assert result.count == 0
    assert result.total == 150
    assert result.has_more is False
    assert result.lines == []


@pytest.mark.asyncio
async def test_get_devserver_logs_empty_logs(multi_server_config, temp_state_dir):
    manager = DevServerManager(multi_server_config, "/test/project")
    process = manager.processes["api"]

    with patch.object(process, "_is_process_alive", return_value=True):
        process.pid = 12345
        process.start_time = 1234567890

        result = manager.get_devserver_logs("api")

        assert result.status == "success"
        assert result.count == 0
        assert result.total == 0
        assert result.has_more is False
        assert result.lines == []


@pytest.mark.asyncio
async def test_get_devserver_logs_concurrent_access(manager_with_logs):
    async def get_logs(offset):
        return manager_with_logs.get_devserver_logs("api", offset=offset, limit=10)

    results = await asyncio.gather(
        get_logs(0),
        get_logs(50),
        get_logs(100),
    )

    assert all(r.status == "success" for r in results)
    assert results[0].lines[0] == "Test log line 149"
    assert results[1].lines[0] == "Test log line 99"
    assert results[2].lines[0] == "Test log line 49"


@pytest.mark.asyncio
async def test_browser_console_messages_pagination(multi_server_config, temp_state_dir):
    pytest.importorskip("playwright")

    from devserver_mcp.types import ExperimentalConfig

    config = multi_server_config
    config.experimental = ExperimentalConfig(playwright=True)
    manager = DevServerManager(config, "/test/project")
    manager._init_playwright_if_enabled()

    if manager._playwright_operator:
        import json

        for i in range(50):
            msg_data = {"type": "log", "text": f"Console message {i}", "args": [], "location": {}}
            manager._playwright_operator._console_messages.append(json.dumps(msg_data))

        result = await manager.playwright_console_messages(offset=10, limit=15)

        assert result["status"] == "success"
        assert result["count"] == 15
        assert result["total"] == 50
        assert result["offset"] == 10
        assert result["has_more"] is True
        assert len(result["messages"]) == 15
        assert result["messages"][0]["text"] == "Console message 39"


@pytest.mark.asyncio
async def test_browser_console_messages_clear_with_pagination(multi_server_config, temp_state_dir):
    pytest.importorskip("playwright")

    from devserver_mcp.types import ExperimentalConfig

    config = multi_server_config
    config.experimental = ExperimentalConfig(playwright=True)
    manager = DevServerManager(config, "/test/project")
    manager._init_playwright_if_enabled()

    if manager._playwright_operator:
        import json

        for i in range(30):
            msg_data = {"type": "log", "text": f"Message {i}", "args": [], "location": {}}
            manager._playwright_operator._console_messages.append(json.dumps(msg_data))

        result = await manager.playwright_console_messages(clear=True, limit=10)

        assert result["status"] == "success"
        assert result["count"] == 10
        assert result["total"] == 30

        result2 = await manager.playwright_console_messages()
        assert result2["total"] == 0
