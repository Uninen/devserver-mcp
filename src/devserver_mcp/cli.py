import contextlib
import os
import signal
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import click
import httpx

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
            response = httpx.get(f"http://localhost:{port}/health/", timeout=0.5)
            if response.status_code == 200:
                return True
        except httpx.RequestError:
            pass
        time.sleep(0.1)
    return False


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Devservers - Development server orchestration"""
    if ctx.invoked_subcommand is None:
        is_running = is_manager_running()
        status = "🟢 Running" if is_running else "🔴 Not running"

        click.echo("Devservers - Development server orchestration\n")
        click.echo(f"Status: {status}")

        if is_running:
            click.echo("Web UI: http://localhost:7912")

        click.echo("\nCommands:")
        click.echo("  devservers start              Start the manager")
        click.echo("  devservers start <project>    Start manager + project servers")
        click.echo("  devservers stop               Stop the manager")
        click.echo("  devservers ui                 Open web UI (starts manager if needed)")
        click.echo("  devservers --help             Show detailed help")


@cli.command()
@click.argument("project", required=False)
def start(project):
    """Start the Devservers manager"""
    if is_manager_running():
        click.echo("⚠️  Devservers manager is already running")
        click.echo("Use 'devservers ui' to open the web interface")
        return

    port = 7912
    pid_file = get_pid_file_path()

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
        click.echo(f"✅ Devservers manager started at http://localhost:{port}")

        # Auto-register current directory's project
        config_path = resolve_config_path("devservers.yml")
        if config_path and Path(config_path).exists():
            try:
                config = load_config(config_path)
                project_id = config.project or Path.cwd().name
                project_name = project_id

                # Register via API
                project_data = {
                    "id": project_id,
                    "name": project_name,
                    "path": str(Path.cwd()),
                    "config_file": "devservers.yml",
                    "last_accessed": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                try:
                    response = httpx.post(f"http://localhost:{port}/api/projects/", json=project_data)
                    if response.status_code == 200:
                        click.echo(f"📁 Registered project: {project_name}")
                except Exception as e:
                    click.echo(f"⚠️  Could not register project: {e}", err=True)
            except Exception as e:
                click.echo(f"⚠️  Could not load config: {e}", err=True)

        if project:
            click.echo(f"🚀 Starting servers for project: {project}")
            # Find the project in the registry
            try:
                response = httpx.get(f"http://localhost:{port}/api/projects/")
                if response.status_code == 200:
                    projects = response.json()
                    matching_project = None
                    for p in projects:
                        if p["id"] == project or p["name"] == project:
                            matching_project = p
                            break

                    if matching_project:
                        # Load the project's config to find autostart servers
                        config_path = Path(matching_project["path"]) / matching_project["config_file"]
                        if config_path.exists():
                            config = load_config(str(config_path))
                            # Start all autostart servers
                            for server_name, server_config in config.servers.items():
                                if server_config.autostart:
                                    click.echo(f"   - {server_name} (autostart)")
                                    try:
                                        response = httpx.post(
                                            f"http://localhost:{port}/api/projects/{matching_project['id']}/servers/{server_name}/start/",
                                            json={"project_id": matching_project["id"]},
                                        )
                                        if response.status_code != 200:
                                            click.echo(f"     ⚠️  Failed to start {server_name}", err=True)
                                    except Exception as e:
                                        click.echo(f"     ⚠️  Error starting {server_name}: {e}", err=True)
                    else:
                        click.echo(f"⚠️  Project '{project}' not found in registry", err=True)
            except Exception as e:
                click.echo(f"⚠️  Error starting project servers: {e}", err=True)
    else:
        click.echo("❌ Failed to start Devservers manager", err=True)
        # Clean up PID file
        pid_file.unlink(missing_ok=True)
        sys.exit(1)


@cli.command()
def stop():
    """Stop the Devservers manager"""
    pid_file = get_pid_file_path()
    status_file = get_status_file_path()

    if not is_manager_running():
        click.echo("⚠️  Devservers manager is not running")
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

        click.echo("⏹️  Devservers manager stopped")
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
