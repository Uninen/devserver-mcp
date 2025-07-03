import tempfile
from pathlib import Path

from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_cli_file_not_found_error():
    """Test CLI behavior when config file is not found."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--config", "/nonexistent/path/config.yml"])

    # Click returns exit code 2 for usage errors
    assert result.exit_code == 2
    assert "Error" in result.output


def test_cli_yaml_parsing_error():
    """Test CLI behavior when config file has invalid YAML."""
    runner = CliRunner()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        f.write("invalid: yaml: content: [")
        f.flush()
        try:
            result = runner.invoke(cli, ["--config", f.name])
            assert result.exit_code == 2  # Click returns exit code 2 for config errors
            assert "Error" in result.output
        finally:
            Path(f.name).unlink()