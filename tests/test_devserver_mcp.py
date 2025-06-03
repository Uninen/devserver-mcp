import sys
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
def mock_manager():
    manager = MagicMock()
    manager.shutdown_all = AsyncMock()
    return manager


@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    mcp.run_async = AsyncMock()
    return mcp


def test_init_with_config(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config, port=8080)

        assert server.config == simple_config
        assert server.port == 8080
        assert server.transport == "streamable-http"
        mock_manager_cls.assert_called_once_with(simple_config)
        mock_create_mcp.assert_called_once_with(mock_manager_cls.return_value)


def test_init_with_config_path():
    with (
        patch("devserver_mcp.load_config") as mock_load_config,
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        mock_config = Config(servers={"test": ServerConfig(command="test", port=3000)})
        mock_load_config.return_value = mock_config
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config_path="/path/to/config.yml")

        assert server.config == mock_config
        mock_load_config.assert_called_once_with("/path/to/config.yml")


def test_init_with_sse_transport(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config, port=8080, transport="sse")

        assert server.config == simple_config
        assert server.port == 8080
        assert server.transport == "sse"
        mock_manager_cls.assert_called_once_with(simple_config)
        mock_create_mcp.assert_called_once_with(mock_manager_cls.return_value)


def test_init_with_neither_config_nor_path():
    with pytest.raises(ValueError, match="Either config_path or config must be provided"):
        DevServerMCP()


def test_init_with_both_config_and_path_prefers_config(simple_config):
    with (
        patch("devserver_mcp.load_config") as mock_load_config,
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
    ):
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config, config_path="/ignored/path")

        assert server.config == simple_config
        mock_load_config.assert_not_called()


def test_is_interactive_terminal_true():
    with patch("devserver_mcp.DevServerManager"), patch("devserver_mcp.create_mcp_server"):
        server = DevServerMCP(config=Config(servers={}))

        with (
            patch.object(sys.stdout, "isatty", return_value=True),
            patch.object(sys.stderr, "isatty", return_value=True),
        ):
            assert server._is_interactive_terminal() is True


def test_is_interactive_terminal_false():
    with patch("devserver_mcp.DevServerManager"), patch("devserver_mcp.create_mcp_server"):
        server = DevServerMCP(config=Config(servers={}))

        with (
            patch.object(sys.stdout, "isatty", return_value=False),
            patch.object(sys.stderr, "isatty", return_value=True),
        ):
            assert server._is_interactive_terminal() is False


@pytest.mark.asyncio
async def test_run_headless_mode(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.configure_silent_logging") as mock_configure_logging,
        patch("devserver_mcp.silence_all_output"),
    ):
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)

        with (
            patch.object(server, "_is_interactive_terminal", return_value=False),
            patch.object(server, "_run_headless") as mock_run_headless,
        ):
            await server.run()

            mock_configure_logging.assert_called_once()
            mock_run_headless.assert_called_once()


@pytest.mark.asyncio
async def test_run_tui_mode(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.configure_silent_logging") as mock_configure_logging,
    ):
        mock_manager_cls.return_value = MagicMock()
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)

        with (
            patch.object(server, "_is_interactive_terminal", return_value=True),
            patch.object(server, "_run_with_tui") as mock_run_with_tui,
        ):
            await server.run()

            mock_configure_logging.assert_called_once()
            mock_run_with_tui.assert_called_once()


@pytest.mark.asyncio
async def test_run_headless():
    with (
        patch("devserver_mcp.DevServerManager"),
        patch("devserver_mcp.create_mcp_server"),
        patch("devserver_mcp.silence_all_output") as mock_silence,
    ):
        server = DevServerMCP(config=Config(servers={}))

        await server._run_headless()

        mock_silence.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_tui_success(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.DevServerTUI") as mock_tui_cls,
    ):
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        mock_tui = MagicMock()
        mock_tui.run_async = AsyncMock()
        mock_tui_cls.return_value = mock_tui

        server = DevServerMCP(config=simple_config, port=8080)

        with patch.object(server, "_cleanup") as mock_cleanup:
            await server._run_with_tui()

            mock_mcp.run_async.assert_called_once_with(transport="streamable-http", port=8080, host="localhost")
            mock_tui_cls.assert_called_once_with(mock_manager, "http://localhost:8080/mcp/", transport="streamable-http")
            mock_tui.run_async.assert_called_once()
            mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_tui_sse_transport(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.DevServerTUI") as mock_tui_cls,
    ):
        mock_manager = MagicMock()
        mock_manager_cls.return_value = mock_manager

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        mock_tui = MagicMock()
        mock_tui.run_async = AsyncMock()
        mock_tui_cls.return_value = mock_tui

        server = DevServerMCP(config=simple_config, port=8080, transport="sse")

        with patch.object(server, "_cleanup") as mock_cleanup:
            await server._run_with_tui()

            mock_mcp.run_async.assert_called_once_with(transport="sse", port=8080, host="localhost")
            mock_tui_cls.assert_called_once_with(mock_manager, "http://localhost:8080/sse/", transport="sse")
            mock_tui.run_async.assert_called_once()
            mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_tui_keyboard_interrupt(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.DevServerTUI") as mock_tui_cls,
    ):
        mock_manager_cls.return_value = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        mock_tui = MagicMock()
        mock_tui.run_async = AsyncMock(side_effect=KeyboardInterrupt())
        mock_tui_cls.return_value = mock_tui

        server = DevServerMCP(config=simple_config)

        with patch.object(server, "_cleanup") as mock_cleanup:
            await server._run_with_tui()
            mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_tui_generic_exception(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.DevServerTUI") as mock_tui_cls,
    ):
        mock_manager_cls.return_value = MagicMock()

        mock_mcp = MagicMock()
        mock_mcp.run_async = AsyncMock()
        mock_create_mcp.return_value = mock_mcp

        mock_tui = MagicMock()
        mock_tui.run_async = AsyncMock(side_effect=RuntimeError("Test error"))
        mock_tui_cls.return_value = mock_tui

        server = DevServerMCP(config=simple_config)

        with patch.object(server, "_cleanup") as mock_cleanup:
            await server._run_with_tui()
            mock_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_with_mcp_task(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.silence_all_output"),
    ):
        mock_manager = MagicMock()
        mock_manager.shutdown_all = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)

        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        server._mcp_task = mock_task

        with patch("asyncio.wait_for") as mock_wait_for:
            await server._cleanup()

            mock_task.cancel.assert_called_once()
            mock_wait_for.assert_called_once_with(mock_task, timeout=0.5)
            mock_manager.shutdown_all.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_with_done_mcp_task(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.silence_all_output"),
    ):
        mock_manager = MagicMock()
        mock_manager.shutdown_all = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)

        mock_task = MagicMock()
        mock_task.done.return_value = True
        server._mcp_task = mock_task

        await server._cleanup()

        mock_task.cancel.assert_not_called()
        mock_manager.shutdown_all.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_without_mcp_task(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.silence_all_output"),
    ):
        mock_manager = MagicMock()
        mock_manager.shutdown_all = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)
        server._mcp_task = None

        await server._cleanup()

        mock_manager.shutdown_all.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_with_timeout_error(simple_config):
    with (
        patch("devserver_mcp.DevServerManager") as mock_manager_cls,
        patch("devserver_mcp.create_mcp_server") as mock_create_mcp,
        patch("devserver_mcp.silence_all_output"),
    ):
        mock_manager = MagicMock()
        mock_manager.shutdown_all = AsyncMock()
        mock_manager_cls.return_value = mock_manager
        mock_create_mcp.return_value = MagicMock()

        server = DevServerMCP(config=simple_config)

        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.cancel = MagicMock()
        server._mcp_task = mock_task

        with patch("asyncio.wait_for", side_effect=TimeoutError()):
            await server._cleanup()

            mock_task.cancel.assert_called_once()
            mock_manager.shutdown_all.assert_called_once()
