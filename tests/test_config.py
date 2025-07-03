import os
import tempfile

import pytest
import yaml

from devserver_mcp.config import load_config
from devserver_mcp.types import Config


def test_load_config_success():
    """Test loading a valid config file."""
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
    """Test loading a non-existent config file."""
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yml")


def test_load_config_with_experimental_section():
    """Test loading config with experimental features."""
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