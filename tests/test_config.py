import os
import tempfile

import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.types import Config


def test_load_config_loads_valid_yaml():
    """Test that a valid YAML config file is loaded correctly."""
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


def test_load_config_raises_file_not_found_for_nonexistent_file():
    """Test that loading a non-existent config file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yml")


def test_load_config_parses_experimental_section():
    """Test that the experimental section is parsed correctly."""
    config_data = {
        "servers": {
            "backend": {
                "command": "python manage.py runserver",
                "port": 8000,
            }
        },
        "experimental": {"playwright": True},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        try:
            config = load_config(f.name)
            assert config.experimental is not None
            assert config.experimental.playwright is True
        finally:
            os.unlink(f.name)