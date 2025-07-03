import json
import signal
from pathlib import Path
from unittest.mock import patch

import yaml
from click.testing import CliRunner

from devserver_mcp.cli import cli


def test_cli_stop_command_stops_manager(temp_home_dir: Path):
    """Test that the CLI 'stop' command successfully stops the running manager."""
    runner = CliRunner()
    
    # Create the PID file that is_manager_running() checks
    pid_file = temp_home_dir / ".devserver-mcp" / "manager.pid"
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(pid_file, "w") as f:
        f.write("12345")
    
    # Also create status.json file for consistency
    status_file = temp_home_dir / ".devserver-mcp" / "status.json"
    status_data = {
        "running": True,
        "pid": 12345,
        "url": "http://localhost:7912",
        "token": "test-token"
    }
    
    with open(status_file, "w") as f:
        json.dump(status_data, f)
    
    # Mock os.kill to simulate a process that gets terminated
    with patch("os.kill") as mock_kill:
        # Configure mock to:
        # 1. Return None for initial check (process exists)
        # 2. Return None for SIGTERM
        # 3. Raise ProcessLookupError on subsequent checks (process terminated)
        call_count = 0
        def kill_side_effect(pid, sig):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return None  # Process exists for first two calls
            else:
                raise ProcessLookupError()  # Process terminated
        
        mock_kill.side_effect = kill_side_effect
        
        result = runner.invoke(cli, ["stop"])
        
        assert result.exit_code == 0
        assert "Devservers manager stopped" in result.output
        # Verify that SIGTERM (15) was sent
        assert mock_kill.call_args_list[1] == ((12345, signal.SIGTERM),)


def test_cli_status_command_shows_manager_status(temp_home_dir: Path):
    """Test that the CLI status command displays the manager's current status."""
    runner = CliRunner()
    
    result = runner.invoke(cli)
    
    assert result.exit_code == 0
    assert "Devservers - Development server orchestration" in result.output
    assert "Status:" in result.output


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


