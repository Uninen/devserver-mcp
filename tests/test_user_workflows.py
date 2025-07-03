import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_user_starts_manager_workflow(temp_home_dir: Path):
    """Test complete user workflow: start manager from CLI."""
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
        assert "DevServer Manager started" in result.output
        mock_popen.assert_called_once()


def test_user_opens_ui_workflow(temp_home_dir: Path):
    """Test complete user workflow: open UI in browser."""
    runner = CliRunner()
    
    with patch("subprocess.Popen") as mock_popen, \
         patch("webbrowser.open") as mock_browser:
        
        mock_process = type('MockProcess', (), {'pid': 12345})()
        mock_popen.return_value = mock_process
        
        result = runner.invoke(cli, ["ui"])
        
        assert result.exit_code == 0
        assert "Opening http://localhost:7912" in result.output
        mock_browser.assert_called_once_with("http://localhost:7912")


def test_user_stops_manager_workflow(temp_home_dir: Path):
    """Test complete user workflow: stop running manager."""
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
        assert "DevServer Manager stopped" in result.output
        mock_kill.assert_called_once_with(12345, 15)


def test_user_checks_status_workflow(temp_home_dir: Path):
    """Test complete user workflow: check manager status."""
    runner = CliRunner()
    
    result = runner.invoke(cli)
    
    assert result.exit_code == 0
    assert "DevServer Manager" in result.output
    assert "Status:" in result.output


def test_user_project_registration_workflow(temp_home_dir: Path):
    """Test complete user workflow: project auto-registration."""
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
        assert "DevServer Manager started" in result.output


def test_file_operations_resilience(temp_home_dir: Path):
    """Test file operations handle corrupted files gracefully."""
    runner = CliRunner()
    
    status_file = temp_home_dir / ".devserver-mcp" / "status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(status_file, "w") as f:
        f.write("invalid json content")
    
    result = runner.invoke(cli)
    
    assert result.exit_code == 0
    assert "not running" in result.output


def test_network_error_resilience(temp_home_dir: Path):
    """Test network operations handle connection errors gracefully."""
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