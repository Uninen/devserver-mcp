import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml
from click.testing import CliRunner
from pydantic import ValidationError

from devserver_mcp import main
from devserver_mcp.config import load_config, resolve_config_path
from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig


def test_config_file_resilience():
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config("/nonexistent/config.yml")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("servers:\n  api:\n    command: 'echo'\n  - invalid yaml")
        f.flush()
        with pytest.raises(yaml.YAMLError):
            load_config(f.name)
        Path(f.name).unlink()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("")
        f.flush()
        with pytest.raises(TypeError, match="argument after \\*\\* must be a mapping"):
            load_config(f.name)
        Path(f.name).unlink()

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".yml", delete=False) as f:
        f.write(b"\x00\x01\x02\x03\xff\xfe")
        f.flush()
        with pytest.raises((UnicodeDecodeError, yaml.YAMLError)):
            load_config(f.name)
        Path(f.name).unlink()


def test_invalid_config_structure():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"other_key": "value"}, f)
        f.flush()
        with pytest.raises(ValidationError):
            load_config(f.name)
        Path(f.name).unlink()

    with pytest.raises(ValidationError):
        ServerConfig.model_validate({})

    with pytest.raises(ValidationError):
        ServerConfig.model_validate({"port": 8000})

    with pytest.raises(ValidationError):
        ServerConfig.model_validate({"command": "echo test"})

    with pytest.raises(ValidationError):
        ServerConfig.model_validate({"command": 123, "port": 8000})

    with pytest.raises(ValidationError):
        ServerConfig.model_validate({"command": None, "port": 8000})

    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        ServerConfig.model_validate({"command": "echo test", "port": 8000.5})


def test_server_config_edge_cases():
    config = ServerConfig.model_validate({"command": "", "port": 8000})
    assert config.command == ""

    config = ServerConfig.model_validate({"command": "   ", "port": 8000})
    assert config.command == "   "

    config = ServerConfig.model_validate({"command": "echo test", "port": -1})
    assert config.port == -1

    config = ServerConfig.model_validate({"command": "echo test", "port": 0})
    assert config.port == 0

    config = ServerConfig.model_validate({"command": "echo test", "port": 99999})
    assert config.port == 99999

    config = ServerConfig.model_validate({"command": "echo test", "port": "8080"})
    assert config.port == 8080

    very_long_command = "echo " + "a" * 10000
    config = ServerConfig(command=very_long_command, port=8000)
    assert config.command == very_long_command


def test_complex_valid_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        config_data = {
            "servers": {
                "backend": {
                    "command": "python manage.py runserver",
                    "working_dir": "./backend",
                    "port": 8000,
                    "prefix_logs": False,
                    "autostart": True,
                },
                "frontend": {"command": "npm run dev", "working_dir": "./frontend", "port": 3000},
                "minimal": {"command": "echo minimal", "port": 9000},
            }
        }
        yaml.dump(config_data, f)
        f.flush()

        config = load_config(f.name)
        assert len(config.servers) == 3

        backend = config.servers["backend"]
        assert backend.command == "python manage.py runserver"
        assert backend.working_dir == "./backend"
        assert backend.port == 8000
        assert backend.prefix_logs is False
        assert backend.autostart is True

        frontend = config.servers["frontend"]
        assert frontend.command == "npm run dev"
        assert frontend.working_dir == "./frontend"
        assert frontend.port == 3000
        assert frontend.prefix_logs is True
        assert frontend.autostart is False

        minimal = config.servers["minimal"]
        assert minimal.command == "echo minimal"
        assert minimal.working_dir == "."
        assert minimal.port == 9000

        Path(f.name).unlink()


def test_manager_edge_cases():
    config_data = {
        "servers": {
            "API": ServerConfig(command="echo api", port=8000),
            "api": ServerConfig(command="echo api2", port=8001),
            "Api": ServerConfig(command="echo api3", port=8002),
        }
    }
    config = Config(**config_data)
    manager = DevServerManager(config)
    assert len(manager.processes) == 1
    assert "api" in manager.processes
    assert manager.processes["api"].config.command == "echo api3"

    config = Config(
        servers={
            "api1": ServerConfig(command="echo test1", port=8000),
            "api2": ServerConfig(command="echo test2", port=8000),
        }
    )
    manager = DevServerManager(config)
    assert len(manager.processes) == 2
    assert manager.processes["api1"].config.port == 8000
    assert manager.processes["api2"].config.port == 8000

    config = Config(servers={"api": ServerConfig(command="echo test", working_dir="/nonexistent/directory", port=8000)})
    manager = DevServerManager(config)
    assert "api" in manager.processes
    assert manager.processes["api"].config.working_dir == "/nonexistent/directory"


def test_resolve_config_path_absolute_and_existing():
    result = resolve_config_path("/absolute/path/config.yml")
    assert result == "/absolute/path/config.yml"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("servers:\n  api:\n    command: 'echo'")
        f.flush()

        result = resolve_config_path(f.name)
        assert result == f.name

        Path(f.name).unlink()


def test_resolve_config_path_search_functionality():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        subdir = temp_path / "project" / "subdir"
        subdir.mkdir(parents=True)

        config_file = temp_path / "project" / "devserver.yml"
        config_file.write_text("servers:\n  api:\n    command: 'echo'")

        original_cwd = Path.cwd()
        try:
            os.chdir(subdir)

            result = resolve_config_path("devserver.yml")
            assert Path(result).resolve() == config_file.resolve()

        finally:
            os.chdir(original_cwd)


def test_resolve_config_path_git_boundary():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        git_root = temp_path / "repo"
        git_root.mkdir()
        (git_root / ".git").mkdir()

        subdir = git_root / "src" / "deep"
        subdir.mkdir(parents=True)

        outside_config = temp_path / "devserver.yml"
        outside_config.write_text("servers:\n  api:\n    command: 'echo'")

        original_cwd = Path.cwd()
        try:
            os.chdir(subdir)

            result = resolve_config_path("devserver.yml")
            assert result == "devserver.yml"

        finally:
            os.chdir(original_cwd)


def test_resolve_config_path_error_handling():
    with patch("devserver_mcp.config.Path.cwd", side_effect=PermissionError("Access denied")):
        result = resolve_config_path("config.yml")
        assert result == "config.yml"

    with patch("devserver_mcp.config.Path.cwd", side_effect=OSError("Filesystem error")):
        result = resolve_config_path("config.yml")
        assert result == "config.yml"

    with patch("pathlib.Path.exists", side_effect=PermissionError("No access")):
        result = resolve_config_path("config.yml")
        assert result == "config.yml"

    mock_path = Mock(spec=Path)
    parents = []
    current_mock = mock_path

    for _ in range(25):
        parent_mock = Mock(spec=Path)
        current_mock.parent = parent_mock
        parents.append(parent_mock)
        current_mock = parent_mock

    current_mock.parent = current_mock

    mock_path.exists.return_value = False
    for parent in parents:
        parent.exists.return_value = False

    with (
        patch("devserver_mcp.config.Path.cwd", return_value=mock_path),
        patch("os.path.isabs", return_value=False),
        patch("os.path.exists", return_value=False),
    ):
        result = resolve_config_path("config.yml")
        assert result == "config.yml"


def test_resolve_config_path_symlink_cycles():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        current = temp_path
        for i in range(25):
            current = current / f"level_{i}"
            current.mkdir()

        original_cwd = Path.cwd()
        try:
            os.chdir(current)

            result = resolve_config_path("config.yml")
            assert result == "config.yml"

        finally:
            os.chdir(original_cwd)


def test_resolve_config_path_unexpected_exceptions():
    with patch("os.path.isabs", side_effect=RuntimeError("Unexpected error")):
        result = resolve_config_path("config.yml")
        assert result == "config.yml"

    with patch("devserver_mcp.config.Path.cwd") as mock_cwd:
        mock_cwd.return_value.__truediv__.side_effect = RuntimeError("Path operation failed")
        result = resolve_config_path("config.yml")
        assert result == "config.yml"


def test_main_function_file_not_found_error():
    runner = CliRunner()

    result = runner.invoke(main, ["--config", "/nonexistent/path/config.yml"])

    assert result.exit_code == 1
    assert "Error: Config file not found" in result.output
    assert "Looked for 'config.yml' in current directory and parent directories" in result.output


def test_main_function_general_config_error():
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"invalid_structure": "missing servers key"}, f)
        f.flush()

        try:
            result = runner.invoke(main, ["--config", f.name])

            assert result.exit_code == 1
            assert "Error loading config:" in result.output
        finally:
            Path(f.name).unlink()


def test_main_function_yaml_parsing_error():
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("servers:\n  api:\n    command: 'echo'\n  - invalid yaml syntax")
        f.flush()

        try:
            result = runner.invoke(main, ["--config", f.name])

            assert result.exit_code == 1
            assert "Error loading config:" in result.output
        finally:
            Path(f.name).unlink()


def test_main_function_with_mocked_file_not_found():
    runner = CliRunner()

    with patch("devserver_mcp.DevServerMCP") as mock_mcp:
        mock_mcp.side_effect = FileNotFoundError("Mocked file not found")

        result = runner.invoke(main, ["--config", "test.yml"])

        assert result.exit_code == 1
        assert "Error: Config file not found" in result.output


def test_main_function_with_mocked_general_exception():
    runner = CliRunner()

    with patch("devserver_mcp.DevServerMCP") as mock_mcp:
        mock_mcp.side_effect = Exception("Mocked general error")

        result = runner.invoke(main, ["--config", "test.yml"])

        assert result.exit_code == 1
        assert "Error loading config: Mocked general error" in result.output
