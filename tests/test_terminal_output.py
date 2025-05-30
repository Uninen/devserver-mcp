import subprocess
import sys
from pathlib import Path


def test_app_startup_has_no_output():
    """Critical: ensures app starts silently for subprocess usage"""
    result = subprocess.run(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=3,
        input="\x03",  # Send Ctrl+C to quit
    )

    assert result.stdout == "", f"App should not output to stdout, but got: {repr(result.stdout)}"
    assert result.stderr == "", f"App should not output to stderr, but got: {repr(result.stderr)}"
    assert result.returncode == 0, f"App should exit cleanly with code 0, but got: {result.returncode}"
