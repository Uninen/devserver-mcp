import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def test_app_startup_has_no_output():
    config_data = {
        "servers": {
            "test": {
                "command": "echo test",
                "port": 8000,
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
        yaml.dump(config_data, f)
        f.flush()

        result = subprocess.run(
            [sys.executable, "src/devserver_mcp/__init__.py", "--config", f.name],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=3,
            input="\x03",  # Send Ctrl+C to quit
        )

    assert result.stdout == "", f"App should not output to stdout, but got: {repr(result.stdout)}"
    assert result.stderr == "", f"App should not output to stderr, but got: {repr(result.stderr)}"
    assert result.returncode == 0, f"App should exit cleanly with code 0, but got: {result.returncode}"
