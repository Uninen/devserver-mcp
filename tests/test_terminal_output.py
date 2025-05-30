import subprocess
import sys
from pathlib import Path


def test_app_startup_has_no_output():
    """Test that starting the app produces no terminal output"""
    # Run the app with a timeout since it's a TUI app
    result = subprocess.run(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=3,  # Let it start then timeout
        input="\x03",  # Send Ctrl+C to quit
    )

    # The app should not output anything to stdout/stderr during normal startup
    assert result.stdout == "", f"App should not output to stdout, but got: {repr(result.stdout)}"
    assert result.stderr == "", f"App should not output to stderr, but got: {repr(result.stderr)}"
    assert result.returncode == 0, f"App should exit cleanly with code 0, but got: {result.returncode}"


def test_app_quit_has_no_output():
    """Test that quitting the app produces no terminal output"""
    # Start the app and immediately send Ctrl+C to quit
    proc = subprocess.Popen(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Give it a moment to start then quit
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate()

    # The app should not output anything during clean shutdown
    assert stdout == "", f"App should not output to stdout during shutdown, but got: {repr(stdout)}"
    assert stderr == "", f"App should not output to stderr during shutdown, but got: {repr(stderr)}"


def test_clean_shutdown_with_ctrl_c():
    """Test that the app handles Ctrl+C cleanly with no output"""
    # Run the app and send Ctrl+C after a brief moment
    result = subprocess.run(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=3,
        input="\x03",  # Send Ctrl+C to quit
    )

    # Verify clean shutdown with no output
    assert result.stdout == "", "App should not output to stdout"
    assert result.stderr == "", "App should not output to stderr"
    assert result.returncode == 0, "App should exit cleanly"
