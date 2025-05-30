import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from devserver_mcp import load_config
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
