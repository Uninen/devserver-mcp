import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_cli_start_command_starts_manager(temp_home_dir: Path):
    """Test that the CLI 'start' command successfully starts the manager."""
    runner = CliRunner()
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("pathlib.Path.cwd", return_value=temp_home_dir):
        
        mock_process = type('MockProcess', (), {
            'pid': 12345,
            'poll': lambda: None,
            'returncode': None
        })()
        mock_popen.return_value = mock_process
        
        result = runner.invoke(cli, ["start"])

        assert result.exit_code == 0
        assert "Devservers manager started" in result.output
        mock_popen.assert_called_once()


def test_cli_ui_command_opens_browser(temp_home_dir: Path):
    """Test that the CLI 'ui' command opens the UI in a web browser."""
    runner = CliRunner()
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("webbrowser.open") as mock_browser:
        
        mock_process = type('MockProcess', (), {'pid': 12345})()
        mock_popen.return_value = mock_process
        
        result = runner.invoke(cli, ["ui"])
        
        assert result.exit_code == 0
        assert "Opening http://localhost:7912" in result.output
        mock_browser.assert_called_once_with("http://localhost:7912")


def test_cli_stop_command_stops_manager(temp_home_dir: Path):
    """Test that the CLI 'stop' command successfully stops the running manager."""
    runner = CliRunner()
    
    status_file = temp_home_dir / ".devserver-mcp" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    
    status_data = {
        "running": True,
        "pid": 12345,
        "url": "http://localhost:7912",
        "token": "test-token"
    }
    
    with open(status_file, "w") as f:
        json.dump(status_data, f)
    
    with patch("os.kill") as mock_kill:
        result = runner.invoke(cli, ["stop"])
        
        assert result.exit_code == 0
        assert "Devservers manager stopped" in result.output
        mock_kill.assert_called_once_with(12345, 15)


def test_cli_status_command_shows_manager_status(temp_home_dir: Path):
    """Test that the CLI status command displays the manager's current status."""
    runner = CliRunner()
    
    result = runner.invoke(cli)
    
    assert result.exit_code == 0
    assert "Devservers - Development server orchestration" in result.output
    assert "Status:" in result.output


def test_cli_start_command_auto_registers_project(temp_home_dir: Path):
    """Test that the CLI 'start' command auto-registers a project."""
    runner = CliRunner()
    project_dir = temp_home_dir / "test-project"
    project_dir.mkdir()
    
    config_file = project_dir / "devservers.yml"
    config_data = {
        "project": "test-project",
        "servers": {
            "django": {
                "command": "python manage.py runserver",
                "port": 8000,
                "autostart": True
            }
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("pathlib.Path.cwd", return_value=project_dir), \
         patch("httpx.post") as mock_post:
        
        mock_process = type('MockProcess', (), {'pid': 12345})()
        mock_popen.return_value = mock_process
        
        mock_response = type('MockResponse', (), {
            'status_code': 200,
            'json': lambda: {"status": "registered"}
        })()
        mock_post.return_value = mock_response
        
        result = runner.invoke(cli, ["start"])
        
        assert result.exit_code == 0
        assert "Devservers manager started" in result.output


def test_cli_handles_corrupted_status_file_gracefully(temp_home_dir: Path):
    """Test that the CLI handles a corrupted status.json file gracefully."""
    runner = CliRunner()
    
    status_file = temp_home_dir / ".devserver-mcp" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(status_file, "w") as f:
        f.write("invalid json content")
    
    result = runner.invoke(cli)
    
    assert result.exit_code == 0
    assert "Status: 🔴 Not running" in result.output


def test_cli_handles_network_errors_gracefully(temp_home_dir: Path):
    """Test that the CLI handles network connection errors gracefully."""
    runner = CliRunner()
    project_dir = temp_home_dir / "test-project"
    project_dir.mkdir()
    
    config_file = project_dir / "devservers.yml"
    config_data = {"project": "test-project", "servers": {}}
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("pathlib.Path.cwd", return_value=project_dir), \
         patch("httpx.post", side_effect=Exception("Connection failed")):
        
        mock_process = type('MockProcess', (), {'pid': 12345})()
        mock_popen.return_value = mock_process
        
        result = runner.invoke(cli, ["start"])
        
        assert result.exit_code == 0