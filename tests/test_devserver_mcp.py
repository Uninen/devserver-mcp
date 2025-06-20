import asyncio
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from pydantic import ValidationError

from devserver_mcp import DevServerMCP
from devserver_mcp.types import Config


def test_init_with_neither_config_nor_path():
    with pytest.raises(ValueError, match="Either config_path or config must be provided"):
        DevServerMCP(_skip_port_check=True)


def test_init_with_config_object(simple_config, temp_state_dir):
    server = DevServerMCP(config=simple_config, port=8080, _skip_port_check=True)
    assert server.manager is not None
    assert server.mcp is not None


def test_init_with_config_path(temp_state_dir):
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        config_path = f.name

    try:
        server = DevServerMCP(config_path=config_path, _skip_port_check=True)
        assert server.manager is not None
        assert server.mcp is not None
    finally:
        Path(config_path).unlink()


def test_is_interactive_terminal_detection():
    server = DevServerMCP(config=Config(servers={}), _skip_port_check=True)

    with (
        patch.object(sys.stdout, "isatty", return_value=False),
        patch.object(sys.stderr, "isatty", return_value=True),
    ):
        assert server._is_interactive_terminal() is False

    with (
        patch.object(sys.stdout, "isatty", return_value=True),
        patch.object(sys.stderr, "isatty", return_value=True),
        patch.dict("os.environ", {}, clear=True),
    ):
        assert server._is_interactive_terminal() is True

    with (
        patch.object(sys.stdout, "isatty", return_value=True),
        patch.object(sys.stderr, "isatty", return_value=True),
        patch.dict("os.environ", {"CI": "true"}),
    ):
        assert server._is_interactive_terminal() is False


@pytest.mark.asyncio
async def test_run_headless_mode(simple_config, temp_state_dir):
    server = DevServerMCP(config=simple_config, port=8081, _skip_port_check=True)

    with patch.object(server, "_is_interactive_terminal", return_value=False):
        run_task = asyncio.create_task(server.run())
        await asyncio.sleep(0.1)
        run_task.cancel()

        with suppress(asyncio.CancelledError):
            await run_task


@pytest.mark.asyncio
async def test_cleanup_stops_running_servers(running_config, temp_state_dir):
    server = DevServerMCP(config=running_config, port=8082, _skip_port_check=True)

    await server.manager.start_server("api")
    assert server.manager.get_server_status("api")["status"] == "running"

    await server._cleanup()

    assert server.manager.get_server_status("api")["status"] == "stopped"


def test_config_validation_invalid_yaml(temp_state_dir):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        config_path = f.name

    try:
        with pytest.raises(yaml.YAMLError):
            DevServerMCP(config_path=config_path, _skip_port_check=True)
    finally:
        Path(config_path).unlink()


def test_config_validation_missing_servers(temp_state_dir):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"not_servers": {}}, f)
        config_path = f.name

    try:
        with pytest.raises(ValidationError):
            DevServerMCP(config_path=config_path, _skip_port_check=True)
    finally:
        Path(config_path).unlink()


@pytest.mark.asyncio
async def test_autostart_servers_on_init(autostart_config, temp_state_dir):
    server = DevServerMCP(config=autostart_config, port=8083, _skip_port_check=True)

    await server.manager.autostart_configured_servers()

    await asyncio.sleep(0.2)

    assert server.manager.get_server_status("autostart")["status"] == "running"
    assert server.manager.get_server_status("manual")["status"] == "stopped"

    await server._cleanup()
