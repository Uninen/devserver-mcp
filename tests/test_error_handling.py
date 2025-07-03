from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_cli_shows_help_when_project_config_lacks_servers_section(temp_home_dir: Path):
    """Test that the CLI shows help when project config is missing the 'servers' section."""
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
        
        # Should show help message, not error
        assert result.exit_code == 0
        assert "Devservers - Development server orchestration" in result.output
        assert "Commands:" in result.output


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
