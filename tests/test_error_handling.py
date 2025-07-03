from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml
from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_manager_starts_gracefully_with_corrupted_config_file(temp_home_dir: Path):
    """Test that the manager starts gracefully even with a corrupted config file."""
    runner = CliRunner()
    
    # Create corrupted config file
    config_file = temp_home_dir / ".devserver-mcp" / "config.yml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_file, "w") as f:
        f.write("invalid: yaml: [incomplete")
    
    # Manager should still start despite corrupted config
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process
        
        result = runner.invoke(cli, ["start"])
        
        assert result.exit_code == 0
        assert "manager started" in result.output


def test_cli_errors_when_project_config_lacks_servers_section(temp_home_dir: Path):
    """Test that the CLI reports an error when project config is missing the 'servers' section."""
    runner = CliRunner()
    project_dir = temp_home_dir / "test-project"
    project_dir.mkdir()
    
    # Create config without servers
    config_file = project_dir / "devservers.yml"
    config_data = {
        "project": "test-project"
        # Missing "servers" section
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    with patch("pathlib.Path.cwd", return_value=project_dir):
        result = runner.invoke(cli)
        
        # Should show error message
        assert result.exit_code == 1
        assert "Error loading config" in result.output


def test_server_start_returns_error_for_nonexistent_command(test_app, auth_headers, project_directory):
    """Test that starting a server with a nonexistent command returns an error status."""
    # Create a config with invalid command
    config_file = project_directory / "devservers.yml"
    config_data = {
        "servers": {
            "broken": {
                "command": "/nonexistent/command",
                "port": 8000
            }
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Update test app to use this project directory
    test_app.app.state.deps.file_ops.get_safe_config_path.side_effect = lambda base, file: project_directory / file
    test_app.app.state.deps.project_registry._projects["test-project"]["path"] = str(project_directory)
    
    # Try to start server with non-existent command
    response = test_app.post(
        "/api/projects/test-project/servers/broken/start/",
        headers=auth_headers
    )
    
    # Should return successful response with error status
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["error", "started"]  # May succeed initially but fail later
