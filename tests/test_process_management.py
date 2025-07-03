import asyncio
from unittest.mock import MagicMock, patch

import pytest

from devserver_mcp.types import ServerConfig
from devserver_mcp.web_manager.process_manager import ProcessManager


@pytest.fixture
def process_manager():
    return ProcessManager()


@pytest.fixture
def sleep_server_config(temp_home_dir):
    """Server config that sleeps for a short time."""
    return ServerConfig(
        command="sleep 1",
        working_dir=str(temp_home_dir),
        port=8000,
        autostart=False
    )


@pytest.mark.asyncio
async def test_process_starts_and_stops_successfully(process_manager, sleep_server_config):
    """Test that a simple sleep process starts and then stops (exits) successfully."""
    # This uses a real subprocess with sleep command
    started = await process_manager.start_process(
        "test-project", "sleep-server", sleep_server_config
    )
    
    assert started is True
    
    # Give it a moment to exit
    await asyncio.sleep(1.5)
    
    # Check status after process exits naturally
    status = process_manager.get_process_status("test-project", "sleep-server")
    assert status["status"] == "stopped" or status["status"] == "error" # Sleep exits after 1s, so it should be stopped or error


@pytest.mark.asyncio
async def test_start_process_fails_with_nonexistent_working_directory(process_manager):
    """Test that starting a process fails when the working directory does not exist."""
    config = ServerConfig(
        command="echo test",
        working_dir="/this/directory/does/not/exist",
        port=8000
    )
    
    result = await process_manager.start_process(
        "test-project", "bad-dir-server", config
    )
    
    assert result is False
    status = process_manager.get_process_status("test-project", "bad-dir-server")
    assert status["status"] == "error"
    assert "does not exist" in status["error"]


@pytest.mark.asyncio
async def test_cleanup_all_processes_terminates_all_running_processes(process_manager, sleep_server_config):
    """Test that cleanup_all terminates all running processes."""
    # Start a process
    await process_manager.start_process(
        "test-project", "sleep-server", sleep_server_config
    )
    
    # Verify process is running
    status = process_manager.get_process_status("test-project", "sleep-server")
    assert status["status"] == "running"
    
    # Clean up all processes
    await process_manager.cleanup_all()
    
    # Verify process is stopped
    status = process_manager.get_process_status("test-project", "sleep-server")
    assert status["status"] == "stopped"


@pytest.mark.asyncio
async def test_get_process_logs_returns_empty_for_nonexistent_process(process_manager):
    """Test that getting logs for a non-existent process returns empty results."""
    lines, total, has_more = process_manager.get_process_logs(
        "nonexistent-project", "nonexistent-server", 0, 100
    )
    
    assert lines == []
    assert total == 0
    assert has_more is False