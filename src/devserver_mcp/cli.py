import contextlib
import json
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import click
import requests

from .config import load_config, resolve_config_path


def get_status_file_path():
    """Get the path to the status file."""
    config_dir = Path.home() / ".devserver-mcp"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "status.json"


def get_pid_file_path():
    """Get the path to the PID file."""
    config_dir = Path.home() / ".devserver-mcp"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "manager.pid"


def is_manager_running():
    """Check if the manager is running."""
    pid_file = get_pid_file_path()
    if not pid_file.exists():
        return False

    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())

        # Check if process is still running
        os.kill(pid, 0)
        return True
    except (ValueError, OSError, ProcessLookupError):
        # PID file exists but process is not running
        pid_file.unlink(missing_ok=True)
        return False


def wait_for_manager(port=7912, timeout=5):
    """Wait for the manager to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=0.5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.1)
    return False


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """DevServer Manager - Development server orchestration"""
    if ctx.invoked_subcommand is None:
        is_running = is_manager_running()
        status = "🟢 Running" if is_running else "🔴 Not running"

        click.echo("DevServer Manager - Development server orchestration\n")
        click.echo(f"Status: {status}")

        if is_running:
            try:
                response = requests.get("http://localhost:7912/api/projects")
                projects = response.json()
                click.echo(f"Projects: {len(projects)} registered")
            except requests.exceptions.RequestException:
                click.echo("Projects: Unable to fetch")
        else:
            click.echo("Projects: 0 registered")

        click.echo("\nCommands:")
        click.echo("  devservers start              Start the manager")
        click.echo("  devservers start <project>    Start manager + project servers")
        click.echo("  devservers stop               Stop the manager")
        click.echo("  devservers ui                 Open web UI (starts manager if needed)")
        click.echo("  devservers --help             Show detailed help")


@cli.command()
@click.argument("project", required=False)
def start(project):
    """Start the DevServer Manager"""
    if is_manager_running():
        click.echo("⚠️  DevServer Manager is already running")
        click.echo("Use 'devservers ui' to open the web interface")
        return

    port = 7912
    pid_file = get_pid_file_path()
    status_file = get_status_file_path()

    # Start the manager in a subprocess
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        [sys.executable, "-m", "devserver_mcp.web_manager"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent process
    )

    # Write PID file
    with open(pid_file, "w") as f:
        f.write(str(process.pid))

    # Wait for manager to be ready
    if wait_for_manager(port):
        click.echo(f"✅ DevServer Manager started at http://localhost:{port}")

        # Write status file
        status_data = {
            "running": True,
            "pid": process.pid,
            "url": f"http://localhost:{port}",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(status_file, "w") as f:
            json.dump(status_data, f, indent=2)

        # Auto-register current directory's project
        config_path = resolve_config_path("devservers.yml")
        if config_path and Path(config_path).exists():
            try:
                config = load_config(config_path)
                project_id = getattr(config, "project", Path.cwd().name)
                project_name = getattr(config, "name", project_id)

                # Register via API
                project_data = {
                    "id": project_id,
                    "name": project_name,
                    "path": str(Path.cwd()),
                    "config_file": "devservers.yml",
                    "last_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                try:
                    response = requests.post(f"http://localhost:{port}/api/projects", json=project_data)
                    if response.status_code == 200:
                        click.echo(f"📁 Registered project: {project_name}")
                except Exception as e:
                    click.echo(f"⚠️  Could not register project: {e}", err=True)
            except Exception as e:
                click.echo(f"⚠️  Could not load config: {e}", err=True)

        if project:
            click.echo(f"🚀 Starting servers for project: {project}")
            click.echo("   (autostart functionality coming soon)")
    else:
        click.echo("❌ Failed to start DevServer Manager", err=True)
        # Clean up PID file
        pid_file.unlink(missing_ok=True)
        sys.exit(1)


@cli.command()
def stop():
    """Stop the DevServer Manager"""
    pid_file = get_pid_file_path()
    status_file = get_status_file_path()

    if not is_manager_running():
        click.echo("⚠️  DevServer Manager is not running")
        return

    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())

        # Send SIGTERM to gracefully stop the process
        os.kill(pid, signal.SIGTERM)

        # Wait for process to stop (max 5 seconds)
        for _ in range(50):
            try:
                os.kill(pid, 0)  # Check if process still exists
                time.sleep(0.1)
            except ProcessLookupError:
                break
        else:
            # Force kill if still running
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)

        # Clean up files
        pid_file.unlink(missing_ok=True)
        status_file.unlink(missing_ok=True)

        click.echo("⏹️  DevServer Manager stopped")
    except Exception as e:
        click.echo(f"❌ Error stopping manager: {e}", err=True)
        sys.exit(1)


@cli.command()
def ui():
    """Open the web UI"""
    port = 7912
    url = f"http://localhost:{port}"

    # Start manager if not running
    if not is_manager_running():
        click.echo("Manager not running. Starting...")
        ctx = click.get_current_context()
        ctx.invoke(start)

        # Give it a moment to fully start
        time.sleep(0.5)

    click.echo(f"🔗 Opening {url} in your browser...")
    webbrowser.open(url)
