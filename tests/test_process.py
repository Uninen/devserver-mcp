import asyncio
import os

import pytest

from devserver_mcp.process import ManagedProcess
from devserver_mcp.types import ServerConfig


@pytest.fixture
def managed_process(simple_server_config, temp_state_manager):
    return ManagedProcess(
        name="test_server", config=simple_server_config, color="blue", state_manager=temp_state_manager
    )


@pytest.mark.asyncio
async def test_process_start_stop_cycle(running_server_config, temp_state_manager):
    process = ManagedProcess("test_server", running_server_config, "blue", temp_state_manager)

    result = await process.start(lambda msg: None)
    assert result is True

    await process.stop()


@pytest.mark.asyncio
async def test_process_handles_command_not_found(temp_state_manager):
    config = ServerConfig(command="nonexistent_command_xyz", working_dir=".", port=12346)
    process = ManagedProcess("test", config, "blue", temp_state_manager)

    log_messages = []
    result = await process.start(lambda msg: log_messages.append(msg))

    assert result is False
    assert process.error is not None


@pytest.mark.asyncio
async def test_process_state_persistence(running_server_config, temp_state_manager):
    process1 = ManagedProcess("test_server", running_server_config, "blue", temp_state_manager)

    result = await process1.start(lambda msg: None)
    assert result is True
    original_pid = process1.pid

    process2 = ManagedProcess("test_server", running_server_config, "blue", temp_state_manager)

    assert process2.pid == original_pid
    assert process2.is_running

    await process2.stop()


@pytest.mark.asyncio
async def test_process_cleanup_on_already_stopped(managed_process):
    await managed_process.stop()
    await managed_process.stop()

    assert managed_process.pid is None
    assert not managed_process.is_running


@pytest.mark.asyncio
async def test_process_output_capture(echo_server_config, temp_state_manager):
    process = ManagedProcess("echo_test", echo_server_config, "blue", temp_state_manager)

    captured_logs = []

    def log_callback(server_name, timestamp, msg):
        captured_logs.append(msg)

    await process.start(log_callback)

    await asyncio.sleep(0.1)

    await process.stop()

    assert any("test output" in log for log in captured_logs)


def test_process_reclaim_cleans_dead_pid(simple_server_config, temp_state_manager):
    temp_state_manager.save_pid("test_server", 99999999)

    process = ManagedProcess("test_server", simple_server_config, "blue", temp_state_manager)

    assert process.pid is None
    assert temp_state_manager.get_pid("test_server") is None


def test_process_reclaim_keeps_live_pid(simple_server_config, temp_state_manager):
    current_pid = os.getpid()
    temp_state_manager.save_pid("test_server", current_pid)

    process = ManagedProcess("test_server", simple_server_config, "blue", temp_state_manager)

    assert process.pid == current_pid
    assert process.start_time is not None
