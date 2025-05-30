from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp.process import ManagedProcess
from devserver_mcp.types import ServerConfig


@pytest.fixture
def server_config():
    return ServerConfig(command="echo hello", working_dir=".", port=12345)


@pytest.fixture
def managed_process(server_config):
    return ManagedProcess(name="test_server", config=server_config, color="blue")


def test_stop_running_process(managed_process):
    """Test stopping a running process"""
    # Mock a running process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    # Call stop
    managed_process.stop()

    # Verify process was terminated
    mock_process.terminate.assert_called_once()

    # Verify cleanup
    assert managed_process.process is None
    assert managed_process.start_time is None


def test_stop_already_stopped_process(managed_process):
    """Test stopping a process that's already stopped"""
    # Process is already None
    managed_process.process = None
    managed_process.start_time = None

    # Should not raise any exception
    managed_process.stop()

    # Should remain None
    assert managed_process.process is None
    assert managed_process.start_time is None


def test_stop_process_with_lookup_error(managed_process):
    """Test stopping a process that raises ProcessLookupError"""
    # Mock a process that raises ProcessLookupError when terminated
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.terminate.side_effect = ProcessLookupError("Process not found")

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    # Should handle the exception gracefully
    managed_process.stop()

    # Verify cleanup still happens
    assert managed_process.process is None
    assert managed_process.start_time is None


def test_stop_process_with_os_error(managed_process):
    """Test stopping a process that raises OSError"""
    # Mock a process that raises OSError when terminated
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.terminate.side_effect = OSError("Operation not permitted")

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    # Should handle the exception gracefully
    managed_process.stop()

    # Verify cleanup still happens
    assert managed_process.process is None
    assert managed_process.start_time is None


def test_is_running_after_stop(managed_process):
    """Test that is_running returns False after stopping"""
    # Mock a running process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    managed_process.process = mock_process

    # Verify it's running before stop
    assert managed_process.is_running is True

    # Stop the process
    managed_process.stop()

    # Verify it's not running after stop
    assert managed_process.is_running is False


def test_status_after_stop(managed_process):
    """Test that status returns 'stopped' after stopping"""
    # Mock a running process
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.returncode = None

    managed_process.process = mock_process
    managed_process.error = None

    # Verify status is running before stop
    assert managed_process.status == "running"

    # Stop the process
    managed_process.stop()

    # Verify status is stopped after stop
    assert managed_process.status == "stopped"


# Tests for start method


@pytest.mark.asyncio
async def test_start_success(managed_process):
    """Test successful process start"""
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        # Mock successful subprocess creation
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.stdout = AsyncMock()
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task") as mock_create_task, patch("asyncio.sleep") as mock_sleep:
            result = await managed_process.start(mock_log_callback)

        # Verify success
        assert result is True
        assert managed_process.process == mock_process
        assert managed_process.start_time is not None
        assert managed_process.error is None

        # Verify subprocess was created correctly
        mock_create_subprocess.assert_called_once()
        mock_create_task.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_start_process_exits_immediately(managed_process):
    """Test when process exits immediately after start"""
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        # Mock process that exits immediately
        mock_process = AsyncMock()
        mock_process.returncode = 1  # Process exited with code 1
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task"), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        # Verify failure
        assert result is False
        assert managed_process.error == "Process exited immediately with code 1"


@pytest.mark.asyncio
async def test_start_exception_handling(managed_process):
    """Test exception handling during start"""
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        # Mock exception during subprocess creation
        mock_create_subprocess.side_effect = FileNotFoundError("Command not found")

        result = await managed_process.start(mock_log_callback)

        # Verify failure with error message
        assert result is False
        assert managed_process.error == "Command not found"


@pytest.mark.asyncio
async def test_start_clears_previous_error(managed_process):
    """Test that start clears any previous error"""
    mock_log_callback = MagicMock()

    # Set an initial error
    managed_process.error = "Previous error"

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task"), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        # Verify error was cleared
        assert result is True
        assert managed_process.error is None


# Tests for status property


def test_status_running(managed_process):
    """Test status when process is running"""
    mock_process = MagicMock()
    mock_process.returncode = None
    managed_process.process = mock_process
    managed_process.error = None

    assert managed_process.status == "running"


def test_status_error(managed_process):
    """Test status when there's an error"""
    managed_process.process = None
    managed_process.error = "Something went wrong"

    assert managed_process.status == "error"


def test_status_stopped(managed_process):
    """Test status when process is stopped"""
    managed_process.process = None
    managed_process.error = None

    assert managed_process.status == "stopped"


def test_status_process_finished(managed_process):
    """Test status when process has finished (returncode is not None)"""
    mock_process = MagicMock()
    mock_process.returncode = 0  # Process finished
    managed_process.process = mock_process
    managed_process.error = None

    assert managed_process.status == "stopped"


def test_status_error_takes_precedence(managed_process):
    """Test that error status takes precedence over stopped"""
    managed_process.process = None
    managed_process.error = "Failed to start"

    assert managed_process.status == "error"


# Tests for is_running property


def test_is_running_true(managed_process):
    """Test is_running when process is active"""
    mock_process = MagicMock()
    mock_process.returncode = None
    managed_process.process = mock_process

    assert managed_process.is_running is True


def test_is_running_false_no_process(managed_process):
    """Test is_running when no process exists"""
    managed_process.process = None

    assert managed_process.is_running is False


def test_is_running_false_process_finished(managed_process):
    """Test is_running when process has finished"""
    mock_process = MagicMock()
    mock_process.returncode = 0
    managed_process.process = mock_process

    assert managed_process.is_running is False
