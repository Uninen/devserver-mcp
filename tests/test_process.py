import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp.process import ManagedProcess
from devserver_mcp.state import StateManager
from devserver_mcp.types import ServerConfig


@pytest.fixture
def server_config():
    return ServerConfig(command="echo hello", working_dir=".", port=12345)


@pytest.fixture
def temp_state_manager():
    with tempfile.TemporaryDirectory() as tmpdir, patch.object(Path, "home", return_value=Path(tmpdir)):
        yield StateManager("/test/project")


@pytest.fixture
def managed_process(server_config, temp_state_manager):
    return ManagedProcess(name="test_server", config=server_config, color="blue", state_manager=temp_state_manager)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
async def test_stop_running_process_unix(managed_process):
    mock_process = AsyncMock()
    mock_process.wait.return_value = None

    managed_process.process = mock_process
    managed_process.pid = 12345
    managed_process.start_time = 1234567890.0

    # Store PID first to simulate a running process
    managed_process.state_manager.save_pid("test_server", 12345)

    with patch("os.killpg") as mock_killpg:
        await managed_process.stop()

        mock_killpg.assert_called_once_with(12345, 15)  # SIGTERM
        mock_process.wait.assert_called()

    assert managed_process.process is None
    assert managed_process.pid is None
    assert managed_process.start_time is None
    assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
async def test_stop_running_process_windows(managed_process):
    mock_process = AsyncMock()
    mock_process.terminate = MagicMock()
    mock_process.wait.return_value = None

    managed_process.process = mock_process
    managed_process.pid = 12345
    managed_process.start_time = 1234567890.0

    # Store PID first to simulate a running process
    managed_process.state_manager.save_pid("test_server", 12345)

    await managed_process.stop()

    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called()

    assert managed_process.process is None
    assert managed_process.pid is None
    assert managed_process.start_time is None
    assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
async def test_stop_already_stopped_process(managed_process):
    await managed_process.stop()

    assert managed_process.process is None
    assert managed_process.pid is None
    assert managed_process.start_time is None
    # Process was never started, so no PID should be stored
    assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
async def test_stop_process_group_already_dead_unix(managed_process):
    mock_process = AsyncMock()
    mock_process.wait.return_value = None

    managed_process.process = mock_process
    managed_process.pid = 12345
    managed_process.start_time = 1234567890.0

    # Store PID first
    managed_process.state_manager.save_pid("test_server", 12345)

    with patch("os.killpg", side_effect=ProcessLookupError):
        await managed_process.stop()

    assert managed_process.process is None
    assert managed_process.pid is None
    assert managed_process.start_time is None
    assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
async def test_stop_force_kill_on_timeout_unix(managed_process):
    mock_process = AsyncMock()
    mock_process.wait.side_effect = asyncio.TimeoutError

    managed_process.process = mock_process
    managed_process.pid = 12345
    managed_process.start_time = 1234567890.0

    # Store PID first
    managed_process.state_manager.save_pid("test_server", 12345)

    with patch("os.killpg") as mock_killpg:
        await managed_process.stop()

        assert mock_killpg.call_count == 2
        mock_killpg.assert_any_call(12345, 15)  # SIGTERM
        mock_killpg.assert_any_call(12345, 9)  # SIGKILL

    assert managed_process.process is None
    assert managed_process.pid is None
    assert managed_process.start_time is None
    assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
async def test_start_success(managed_process):
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""  # Ensure _read_output loop terminates
        mock_create_subprocess.return_value = mock_process

        with (
            patch("asyncio.create_task", side_effect=asyncio.create_task) as mock_create_task,
            patch("asyncio.sleep") as mock_sleep,
        ):
            result = await managed_process.start(mock_log_callback)

        assert result is True
        assert managed_process.process == mock_process
        assert managed_process.pid == 12345
        assert managed_process.start_time is not None
        assert managed_process.error is None
        assert managed_process.state_manager.get_pid("test_server") == 12345

        mock_create_subprocess.assert_called_once()
        mock_create_task.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_start_process_exits_immediately(managed_process):
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.pid = 12345
        mock_process.returncode = 1  # Process exited with code 1
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task", side_effect=asyncio.create_task), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        assert result is False
        assert managed_process.error == "Process exited immediately with code 1"
        assert managed_process.pid is None
        assert managed_process.state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
async def test_start_exception_handling(managed_process):
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_create_subprocess.side_effect = FileNotFoundError("Command not found")

        result = await managed_process.start(mock_log_callback)

        assert result is False
        assert managed_process.error == "Command not found"


@pytest.mark.asyncio
async def test_start_clears_previous_error(managed_process):
    mock_log_callback = MagicMock()

    managed_process.error = "Previous error"

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task", side_effect=asyncio.create_task), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        assert result is True
        assert managed_process.error is None


def test_reclaim_existing_process_with_live_pid(server_config, temp_state_manager):
    # First, store a PID
    temp_state_manager.save_pid("test_server", 12345)

    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None  # Process is alive

        process = ManagedProcess("test_server", server_config, "blue", temp_state_manager)

        assert process.pid == 12345
        assert process.start_time is not None
        mock_kill.assert_called_once_with(12345, 0)


def test_reclaim_existing_process_with_dead_pid(server_config, temp_state_manager):
    # First, store a PID
    temp_state_manager.save_pid("test_server", 12345)

    with patch("os.kill") as mock_kill:
        mock_kill.side_effect = ProcessLookupError  # Process is dead

        process = ManagedProcess("test_server", server_config, "blue", temp_state_manager)

        assert process.pid is None
        assert process.start_time is None
        assert temp_state_manager.get_pid("test_server") is None
        mock_kill.assert_called_once_with(12345, 0)


def test_reclaim_existing_process_no_stored_pid(server_config, temp_state_manager):
    # Don't store any PID

    process = ManagedProcess("test_server", server_config, "blue", temp_state_manager)

    assert process.pid is None
    assert process.start_time is None
    assert temp_state_manager.get_pid("test_server") is None


@pytest.mark.asyncio
async def test_start_with_already_reclaimed_process(server_config, temp_state_manager):
    # Store a PID and simulate live process
    temp_state_manager.save_pid("test_server", 12345)

    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None  # Process is alive

        process = ManagedProcess("test_server", server_config, "blue", temp_state_manager)

        assert process.is_running

        mock_log_callback = MagicMock()
        result = await process.start(mock_log_callback)

        assert result is True


def test_is_running_property(managed_process):
    # Test with no PID
    assert managed_process.is_running is False

    # Test with live process
    managed_process.pid = 12345
    with patch("os.kill") as mock_kill:
        mock_kill.return_value = None
        assert managed_process.is_running is True
        mock_kill.assert_called_with(12345, 0)

    # Test with dead process
    with patch("os.kill", side_effect=ProcessLookupError):
        assert managed_process.is_running is False
