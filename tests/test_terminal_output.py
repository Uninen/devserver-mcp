import socket
import subprocess
import sys
import tempfile
import threading
import time
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

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            free_port = s.getsockname()[1]

        result = subprocess.run(
            [sys.executable, "src/devserver_mcp/__init__.py", "--config", f.name, "--port", str(free_port)],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            timeout=3,
            input="\x03",
        )

    assert result.stdout == "", f"App should not output to stdout, but got: {repr(result.stdout)}"
    assert result.stderr == "", f"App should not output to stderr, but got: {repr(result.stderr)}"
    assert result.returncode == 0, f"App should exit cleanly with code 0, but got: {result.returncode}"


def test_port_conflict_shows_error_message():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("localhost", port))
    server_socket.listen(1)

    def keep_port_busy():
        try:
            while True:
                time.sleep(0.1)
        except Exception:
            pass

    server_thread = threading.Thread(target=keep_port_busy, daemon=True)
    server_thread.start()

    try:
        config_data = {
            "servers": {
                "test": {
                    "command": "echo test",
                    "port": port,
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            result = subprocess.run(
                [sys.executable, "src/devserver_mcp/__init__.py", "--config", f.name, "--port", str(port)],
                cwd=Path.cwd(),
                capture_output=True,
                text=True,
                timeout=3,
                input="\x03",
            )

        assert result.returncode == 1, f"App should exit with code 1 when port is taken, got: {result.returncode}"
        assert "port" in result.stderr.lower() or "address" in result.stderr.lower(), (
            f"Error message should mention port conflict, but got stderr: {repr(result.stderr)}"
        )

    finally:
        server_socket.close()
