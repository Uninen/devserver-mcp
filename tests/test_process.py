import asyncio
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


@pytest.mark.asyncio
async def test_stop_running_process(managed_process):
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.wait.return_value = None  # wait() is awaited in SUT
    mock_process.terminate = MagicMock()  # terminate() is called synchronously in SUT

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    await managed_process.stop()

    mock_process.terminate.assert_called_once()
    mock_process.wait.assert_called()

    assert managed_process.process is None
    assert managed_process.start_time is None


@pytest.mark.asyncio
async def test_stop_already_stopped_process(managed_process):
    managed_process.process = None
    managed_process.start_time = None

    await managed_process.stop()

    assert managed_process.process is None
    assert managed_process.start_time is None


@pytest.mark.asyncio
async def test_stop_process_with_lookup_error(managed_process):
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.terminate = MagicMock(
        side_effect=ProcessLookupError("Process not found")
    )  # terminate() is called synchronously in SUT

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    await managed_process.stop()

    assert managed_process.process is None
    assert managed_process.start_time is None


@pytest.mark.asyncio
async def test_stop_process_with_os_error(managed_process):
    mock_process = AsyncMock()
    mock_process.pid = 12345
    mock_process.returncode = None
    mock_process.terminate = MagicMock(
        side_effect=OSError("Operation not permitted")
    )  # terminate() is called synchronously in SUT

    managed_process.process = mock_process
    managed_process.start_time = 1234567890.0

    await managed_process.stop()

    assert managed_process.process is None
    assert managed_process.start_time is None


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_start_success(managed_process):
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = None
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
        assert managed_process.start_time is not None
        assert managed_process.error is None

        mock_create_subprocess.assert_called_once()
        mock_create_task.assert_called_once()
        mock_sleep.assert_called_once_with(0.5)


@pytest.mark.asyncio
async def test_start_process_exits_immediately(managed_process):
    mock_log_callback = MagicMock()

    with patch("asyncio.create_subprocess_shell") as mock_create_subprocess:
        mock_process = AsyncMock()
        mock_process.returncode = 1  # Process exited with code 1
        mock_process.stdout = AsyncMock()  # If _read_output runs, stdout might be accessed
        mock_process.stdout.readline.return_value = b""  # Ensure _read_output loop terminates
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task", side_effect=asyncio.create_task), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        assert result is False
        assert managed_process.error == "Process exited immediately with code 1"


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
        mock_process.stdout = AsyncMock()  # If _read_output runs, stdout might be accessed
        mock_process.stdout.readline.return_value = b""  # Ensure _read_output loop terminates
        mock_create_subprocess.return_value = mock_process

        with patch("asyncio.create_task", side_effect=asyncio.create_task), patch("asyncio.sleep"):
            result = await managed_process.start(mock_log_callback)

        assert result is True
        assert managed_process.error is None
