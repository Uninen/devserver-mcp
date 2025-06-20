import asyncio
import contextlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from devserver_mcp import DevServerMCP
from devserver_mcp.types import Config, ServerConfig


@pytest.fixture
def simple_config():
    return Config(
        servers={
            "api": ServerConfig(command="echo hello", working_dir=".", port=12345),
        }
    )


@pytest.fixture
def temp_state_dir():
    with tempfile.TemporaryDirectory() as tmpdir, patch.object(Path, "home", return_value=Path(tmpdir)):
        yield tmpdir


def test_init_with_neither_config_nor_path():
    with pytest.raises(ValueError, match="Either config_path or config must be provided"):
        DevServerMCP(_skip_port_check=True)


@pytest.mark.asyncio
async def test_run_headless_mode(simple_config, temp_state_dir):
    # Mock only system boundaries
    with (
        patch("asyncio.create_subprocess_shell") as mock_create_subprocess,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        # Mock subprocess for servers
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_create_subprocess.return_value = mock_process

        # Mock MCP server
        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        server = DevServerMCP(config=simple_config, port=8080, _skip_port_check=True)

        # Test run method (which will run headless since we're not in interactive terminal)
        with patch.object(server, "_is_interactive_terminal", return_value=False):
            run_task = asyncio.create_task(server.run())

            # Cancel after a short time
            await asyncio.sleep(0.1)
            run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await run_task


def test_is_interactive_terminal_true():
    with (
        patch.object(sys.stdout, "isatty", return_value=True),
        patch.object(sys.stderr, "isatty", return_value=True),
        patch.dict("os.environ", {}, clear=True),
    ):
        server = DevServerMCP(config=Config(servers={}), _skip_port_check=True)
        assert server._is_interactive_terminal() is True


def test_is_interactive_terminal_false():
    with (
        patch.object(sys.stdout, "isatty", return_value=False),
        patch.object(sys.stderr, "isatty", return_value=True),
        patch.dict("os.environ", {}, clear=True),
    ):
        server = DevServerMCP(config=Config(servers={}), _skip_port_check=True)
        assert server._is_interactive_terminal() is False


@pytest.mark.asyncio
async def test_cleanup_with_running_servers(simple_config, temp_state_dir):
    with (
        patch("asyncio.create_subprocess_shell") as mock_create_subprocess,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        # Mock subprocess
        mock_process = AsyncMock()
        mock_process.returncode = None
        mock_process.pid = 12345
        mock_process.stdout = AsyncMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.wait.return_value = None
        mock_process.terminate = MagicMock()
        mock_create_subprocess.return_value = mock_process

        # Mock MCP
        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        server = DevServerMCP(config=simple_config, port=8080, _skip_port_check=True)

        # Start a server
        with patch("asyncio.sleep"), patch("os.kill", return_value=None):
            await server.manager.start_server("api")

        # Verify server started
        assert server.manager.processes["api"].pid == 12345

        # Run cleanup - need to mock both os.kill and os.killpg for the stop process
        with (
            patch("os.killpg") if sys.platform != "win32" else patch.object(mock_process, "terminate"),
            patch("os.kill", return_value=None),
            patch("asyncio.sleep"),
        ):
            await server._cleanup()

        # Verify process was stopped
        assert server.manager.processes["api"].pid is None


def test_config_validation_invalid_yaml(temp_state_dir):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        config_path = f.name

    try:
        from yaml import YAMLError

        with pytest.raises(YAMLError):
            DevServerMCP(config_path=config_path, _skip_port_check=True)
    finally:
        Path(config_path).unlink()


def test_config_validation_missing_servers(temp_state_dir):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("not_servers: {}")
        config_path = f.name

    try:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DevServerMCP(config_path=config_path, _skip_port_check=True)
    finally:
        Path(config_path).unlink()
