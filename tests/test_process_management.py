import asyncio
from unittest.mock import MagicMock, patch

import pytest

from devserver_mcp.types import ServerConfig
from devserver_mcp.web_manager.process_manager import ProcessManager


@pytest.fixture
def process_manager():
    return ProcessManager()


@pytest.fixture
def echo_server_config(temp_home_dir):
    """Server config with a simple echo command that exits quickly."""
    return ServerConfig(
        command="echo 'test server output'",
        working_dir=str(temp_home_dir),
        port=8000,
        autostart=False
    )


@pytest.mark.asyncio
async def test_start_and_stop_echo_process(process_manager, echo_server_config):
    """Test starting and stopping a simple echo process."""
    # This uses a real subprocess with echo command
    result = await process_manager.start_process(
        "test-project", "echo-server", echo_server_config
    )
    
    assert result is True
    
    # Wait a bit for echo to complete
    await asyncio.sleep(0.1)
    
    # Check status after process exits naturally
    status = process_manager.get_process_status("test-project", "echo-server")
    assert status["status"] in ["stopped", "error"]  # Echo exits immediately


@pytest.mark.asyncio
async def test_start_process_nonexistent_directory(process_manager):
    """Test starting a process with non-existent working directory."""
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
async def test_cleanup_all_processes(process_manager, echo_server_config):
    """Test cleanup of all processes."""
    # Start a process
    await process_manager.start_process(
        "test-project", "echo-server", echo_server_config
    )
    
    # Clean up all processes
    await process_manager.cleanup_all()
    
    # Verify no processes remain
    assert len(process_manager.processes) == 0


@pytest.mark.asyncio
async def test_get_process_logs_no_process(process_manager):
    """Test getting logs for non-existent process."""
    lines, total, has_more = process_manager.get_process_logs(
        "nonexistent-project", "nonexistent-server", 0, 100
    )
    
    assert lines is None
    assert total == 0
    assert has_more is False