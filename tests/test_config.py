import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from devserver_mcp.config import load_config, resolve_config_path
from devserver_mcp.types import Config, ServerConfig


def test_load_config_success():
    config_data = {
        "servers": {
            "backend": {
                "command": "python manage.py runserver",
                "working_dir": ".",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        try:
            config = load_config(f.name)
            assert isinstance(config, Config)
            assert "backend" in config.servers
            assert config.servers["backend"].command == "python manage.py runserver"
            assert config.servers["backend"].port == 8000
        finally:
            os.unlink(f.name)


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yml")


def test_resolve_config_path_absolute():
    with tempfile.NamedTemporaryFile(suffix=".yml") as f:
        result = resolve_config_path(f.name)
        assert result == f.name


def test_resolve_config_path_relative_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_file = Path(tmpdir) / "test.yml"
        config_file.touch()

        with patch("devserver_mcp.config.Path.cwd", return_value=Path(tmpdir)):
            result = resolve_config_path("test.yml")
            assert result == str(config_file)


def test_resolve_config_path_not_exists():
    result = resolve_config_path("nonexistent.yml")
    assert result == "nonexistent.yml"


def test_resolve_config_path_in_parent_directory():
    result = resolve_config_path("devservers.yml")
    assert result == "devservers.yml"


def test_resolve_config_path_permission_error():
    with patch("devserver_mcp.config.Path.cwd") as mock_cwd:
        mock_cwd.side_effect = PermissionError()
        result = resolve_config_path("test.yml")
        assert result == "test.yml"


def test_resolve_config_path_max_depth():
    deep_path = Path("/") / "/".join(["deep"] * 25)

    with (
        patch("devserver_mcp.config.Path.cwd", return_value=deep_path),
        patch.object(Path, "exists", return_value=False),
    ):
        result = resolve_config_path("test.yml")
        assert result == "test.yml"


def test_config_model_validation():
    config_data = {
        "servers": {
            "backend": {
                "command": "python manage.py runserver",
                "port": 8000,
                "prefix_logs": False,
                "autostart": True,
            }
        }
    }

    config = Config(**config_data)  # type: ignore
    server = config.servers["backend"]

    assert isinstance(server, ServerConfig)
    assert server.command == "python manage.py runserver"
    assert server.working_dir == "."
    assert server.port == 8000
    assert server.prefix_logs is False
    assert server.autostart is True
