from unittest.mock import patch

from click.testing import CliRunner

from devserver_mcp import main


def test_cli_default_transport():
    runner = CliRunner()

    with patch("devserver_mcp.DevServerMCP") as mock_devserver_cls:
        mock_devserver_cls.return_value.run = lambda: None

        runner.invoke(main, ["--config", "devservers.yml"])

        mock_devserver_cls.assert_called_once_with(config_path="devservers.yml", port=3001, transport="streamable-http")


def test_cli_sse_flag():
    runner = CliRunner()

    with patch("devserver_mcp.DevServerMCP") as mock_devserver_cls:
        mock_devserver_cls.return_value.run = lambda: None

        runner.invoke(main, ["--sse"])

        # Should use default config file with SSE transport
        assert mock_devserver_cls.call_args[1]["transport"] == "sse"


def test_cli_custom_port():
    runner = CliRunner()

    with patch("devserver_mcp.DevServerMCP") as mock_devserver_cls:
        mock_devserver_cls.return_value.run = lambda: None

        runner.invoke(main, ["--port", "8080"])

        assert mock_devserver_cls.call_args[1]["port"] == 8080


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "--config" in result.output
    assert "--port" in result.output
    assert "--sse" in result.output
