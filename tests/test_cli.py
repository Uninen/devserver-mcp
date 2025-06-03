from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from devserver_mcp import main


def test_cli_default_transport():
    runner = CliRunner()
    
    with (
        patch("devserver_mcp.resolve_config_path") as mock_resolve,
        patch("devserver_mcp.DevServerMCP") as mock_devserver_cls,
        patch("asyncio.new_event_loop"),
        patch("asyncio.set_event_loop"),
    ):
        mock_resolve.return_value = "devservers.yml"
        mock_instance = MagicMock()
        mock_devserver_cls.return_value = mock_instance
        
        runner.invoke(main, ["--config", "devservers.yml"])
        
        mock_devserver_cls.assert_called_once_with(
            config_path="devservers.yml", 
            port=3001,
            transport="streamable-http"
        )


def test_cli_sse_flag():
    runner = CliRunner()
    
    with (
        patch("devserver_mcp.resolve_config_path") as mock_resolve,
        patch("devserver_mcp.DevServerMCP") as mock_devserver_cls,
        patch("asyncio.new_event_loop"),
        patch("asyncio.set_event_loop"),
    ):
        mock_resolve.return_value = "devservers.yml"
        mock_instance = MagicMock()
        mock_devserver_cls.return_value = mock_instance
        
        runner.invoke(main, ["--sse"])
        
        mock_devserver_cls.assert_called_once_with(
            config_path="devservers.yml", 
            port=3001,
            transport="sse"
        )


def test_cli_sse_flag_with_custom_port():
    runner = CliRunner()
    
    with (
        patch("devserver_mcp.resolve_config_path") as mock_resolve,
        patch("devserver_mcp.DevServerMCP") as mock_devserver_cls,
        patch("asyncio.new_event_loop"),
        patch("asyncio.set_event_loop"),
    ):
        mock_resolve.return_value = "devservers.yml"
        mock_instance = MagicMock()
        mock_devserver_cls.return_value = mock_instance
        
        runner.invoke(main, ["--sse", "--port", "8080"])
        
        mock_devserver_cls.assert_called_once_with(
            config_path="devservers.yml", 
            port=8080,
            transport="sse"
        )


def test_cli_help_shows_sse_option():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    
    assert result.exit_code == 0
    assert "--sse" in result.output
    assert "Use SSE transport instead of streamable-http" in result.output