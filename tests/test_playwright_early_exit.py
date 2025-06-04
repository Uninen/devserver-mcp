import contextlib
import tempfile
from unittest.mock import patch

import yaml

from devserver_mcp import DevServerMCP


def test_app_exits_early_when_playwright_missing():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        with (
            patch("devserver_mcp.playwright.PLAYWRIGHT_AVAILABLE", False),
            patch("click.echo") as mock_echo,
            patch("sys.exit") as mock_exit,
        ):
            with contextlib.suppress(SystemExit):
                DevServerMCP(config_path=f.name, port=3001)

            mock_echo.assert_called()
            call_args = mock_echo.call_args[0][0]
            assert "Error:" in call_args
            assert "playwright" in call_args.lower()
            assert "pip install playwright" in call_args

            mock_exit.assert_called_with(1)


def test_app_exits_on_playwright_import_error():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        original_import = __builtins__["__import__"]

        def mock_import(name, *args, **kwargs):
            if "devserver_mcp.playwright" in name:
                raise ImportError("No module named 'playwright'")
            return original_import(name, *args, **kwargs)

        with (
            patch("builtins.__import__", side_effect=mock_import),
            patch("click.echo") as mock_echo,
            patch("sys.exit") as mock_exit,
        ):
            with contextlib.suppress(SystemExit):
                DevServerMCP(config_path=f.name, port=3001)

            mock_echo.assert_called()
            assert mock_exit.called


def test_app_starts_normally_when_playwright_disabled():
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
        f.flush()

        with (
            patch("devserver_mcp.playwright.PLAYWRIGHT_AVAILABLE", False),
            patch("sys.exit") as mock_exit,
        ):
            mcp_server = DevServerMCP(config_path=f.name, port=3001)

            mock_exit.assert_not_called()

            assert mcp_server.manager is not None
            assert mcp_server.manager.playwright_enabled is False or mcp_server.manager.playwright_enabled is None


def test_error_message_format():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        with (
            patch("devserver_mcp.playwright.PLAYWRIGHT_AVAILABLE", False),
            patch("click.echo") as mock_echo,
            patch("sys.exit"),
        ):
            with contextlib.suppress(SystemExit):
                DevServerMCP(config_path=f.name, port=3001)

            _, kwargs = mock_echo.call_args
            assert kwargs.get("err") is True
