import tempfile
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner
from pydantic import ValidationError

from devserver_mcp import main
from devserver_mcp.config import load_config


def test_load_config_invalid_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("servers:\n  api:\n    command: 'echo'\n  - invalid yaml")
        f.flush()
        with pytest.raises(yaml.YAMLError):
            load_config(f.name)
        Path(f.name).unlink()


def test_load_config_invalid_structure():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump({"other_key": "value"}, f)
        f.flush()
        with pytest.raises(ValidationError):
            load_config(f.name)
        Path(f.name).unlink()


def test_main_function_file_not_found_error():
    runner = CliRunner()
    result = runner.invoke(main, ["--config", "/nonexistent/path/config.yml"])

    assert result.exit_code == 1
    assert "Error: Config file not found" in result.output
    assert "Looked for 'config.yml' in current directory and parent directories" in result.output


def test_main_function_yaml_parsing_error():
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        f.flush()
        try:
            result = runner.invoke(main, ["--config", f.name])
            assert result.exit_code == 1
            assert "Error loading config" in result.output
        finally:
            Path(f.name).unlink()
