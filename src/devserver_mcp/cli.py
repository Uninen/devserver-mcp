import json
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
    except ValueError:
        # PID file is corrupted
        pid_file.unlink(missing_ok=True)
        return False
    except ProcessLookupError:
        # Process is not running
        pid_file.unlink(missing_ok=True)
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        # Other OS-level errors
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
        except httpx.ConnectError:
            # Server not yet listening
            pass
        except httpx.TimeoutException:
            # Request timed out, server might be overloaded
            pass
        except httpx.RequestError:
            # Other request errors
            pass
        except Exception:
            # Unexpected errors
            pass
        time.sleep(0.1)
    return False


def get_bearer_token():
    """Get the bearer token from the status file."""
    status_file = get_status_file_path()
    if status_file.exists():
        try:
            with open(status_file) as f:
                status = json.load(f)
                return status.get("bearer_token")
        except json.JSONDecodeError:
            # Status file is corrupted
            return None
        except PermissionError:
            # Can't read status file
            return None
        except Exception:
            # Other unexpected errors
            return None
    return None


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
    try:
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
    except PermissionError:
        click.echo("❌ Permission denied. Please check your system permissions.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Failed to start manager process: {e}", err=True)
        sys.exit(1)

    # Wait for manager to be ready
    if wait_for_manager(port):
        click.echo(f"✅ Devservers manager started at http://localhost:{port}")

        # Get bearer token for API calls
        bearer_token = get_bearer_token()
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}

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
                    response = httpx.post(f"http://localhost:{port}/api/projects/", json=project_data, headers=headers)
                    if response.status_code == 200:
                        click.echo(f"📁 Registered project: {project_name}")
                    elif response.status_code == 401:
                        click.echo("⚠️  Authentication failed. Try restarting the manager.", err=True)
                except Exception as e:
                    click.echo(f"⚠️  Could not register project: {e}", err=True)
            except Exception as e:
                click.echo(f"⚠️  Could not load config: {e}", err=True)

        if project:
            click.echo(f"🚀 Starting servers for project: {project}")
            # Find the project in the registry
            try:
                response = httpx.get(f"http://localhost:{port}/api/projects/", headers=headers)
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
                                            headers=headers,
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
    except ValueError:
        click.echo("❌ PID file is corrupted. Please manually check for running processes.", err=True)
        pid_file.unlink(missing_ok=True)
        sys.exit(1)
    except PermissionError:
        click.echo("❌ Permission denied reading PID file. Please check file permissions.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error reading PID file: {e}", err=True)
        sys.exit(1)

    try:
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
            try:
                os.kill(pid, signal.SIGKILL)
                click.echo("⚠️  Manager did not stop gracefully, forced termination")
            except ProcessLookupError:
                pass  # Already dead
            except PermissionError:
                click.echo("❌ Permission denied. Cannot stop the manager process.", err=True)
                sys.exit(1)

        # Clean up files
        pid_file.unlink(missing_ok=True)
        status_file.unlink(missing_ok=True)

        click.echo("⏹️  Devservers manager stopped")
    except ProcessLookupError:
        click.echo("⚠️  Manager process was not running")
        pid_file.unlink(missing_ok=True)
        status_file.unlink(missing_ok=True)
    except PermissionError:
        click.echo("❌ Permission denied. Cannot stop the manager process.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error stopping manager: {e}", err=True)
        sys.exit(1)


@cli.command()
def ui():
    """Open the web UI"""
    port = 7912
    url = f"http://localhost:{port}"

    # Start manager if not running
    if not is_manager_running():
        click.echo("Manager not running. Starting...")
        try:
            ctx = click.get_current_context()
            ctx.invoke(start)

            # Give it a moment to fully start
            time.sleep(0.5)
        except Exception as e:
            click.echo(f"❌ Failed to start manager: {e}", err=True)
            sys.exit(1)

    try:
        click.echo(f"🔗 Opening {url} in your browser...")
        webbrowser.open(url)
    except Exception as e:
        click.echo(f"❌ Failed to open browser: {e}", err=True)
        click.echo(f"Please manually open {url} in your browser.")
