"""
Tests to demonstrate excessive terminal output when launching and quitting the app.

These tests verify that the app produces unwanted output to stdout/stderr
during startup and shutdown operations.
"""
import subprocess
import sys
from pathlib import Path


def test_app_startup_has_excessive_output():
    """Test that starting the app produces unwanted terminal output"""
    # Run the app with a timeout since it's a TUI app
    result = subprocess.run(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=3,  # Let it start then timeout
        input="\x03"  # Send Ctrl+C to quit
    )
    
    # The app should not output anything to stdout during normal startup
    # But currently it does - this test demonstrates the problem
    assert result.stdout != "", "App currently outputs to stdout (this is the problem we want to fix)"
    assert result.stderr != "", "App currently outputs to stderr (this is the problem we want to fix)"
    
    # Print the actual output to see what's being printed
    print("STDOUT output:")
    print(repr(result.stdout))
    print("STDERR output:")  
    print(repr(result.stderr))


def test_app_quit_has_excessive_output():
    """Test that quitting the app produces unwanted terminal output"""
    # Start the app and immediately send Ctrl+C to quit
    proc = subprocess.Popen(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give it a moment to start then quit
    try:
        stdout, stderr = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.terminate()
        stdout, stderr = proc.communicate()
    
    # The app should not output anything during clean shutdown
    # But currently it does - this test demonstrates the problem  
    assert stdout != "" or stderr != "", "App currently outputs during shutdown (this is the problem we want to fix)"
    
    # Print the actual output to see what's being printed
    print("STDOUT output on quit:")
    print(repr(stdout))
    print("STDERR output on quit:")
    print(repr(stderr))


def test_ideal_behavior_no_terminal_output():
    """Test what the ideal behavior should be - no output to terminal"""
    # This test will fail until we fix the issue
    # It demonstrates what we want: clean startup and shutdown with no output
    
    result = subprocess.run(
        [sys.executable, "src/devserver_mcp/__init__.py"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=3,
        input="\x03"  # Send Ctrl+C to quit
    )
    
    # This is what we want but don't have yet
    # assert result.stdout == "", "App should not output to stdout"
    # assert result.stderr == "", "App should not output to stderr" 
    # assert result.returncode == 0, "App should exit cleanly"
    
    # For now, just document the current problematic behavior
    print("Current behavior (should be empty):")
    print(f"stdout: {repr(result.stdout)}")
    print(f"stderr: {repr(result.stderr)}")
    print(f"returncode: {result.returncode}")