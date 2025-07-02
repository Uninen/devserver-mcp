import sys
import webbrowser
from pathlib import Path

import click

from .config import load_config, resolve_config_path
from .web_manager.app import project_registry
from .web_manager.server import start_manager


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """DevServer Manager - Development server orchestration"""
    if ctx.invoked_subcommand is None:
        click.echo("DevServer Manager - Development server orchestration\n")
        click.echo("Status: 🔴 Not running")
        click.echo(f"Projects: {len(project_registry)} registered")
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
    click.echo("✅ DevServer Manager starting at http://localhost:7912")

    config_path = resolve_config_path("devservers.yml")
    if config_path and Path(config_path).exists():
        try:
            config = load_config(config_path)
            project_id = getattr(config, "project", Path.cwd().name)
            project_name = getattr(config, "name", project_id)

            project_registry[project_id] = {
                "id": project_id,
                "name": project_name,
                "path": str(Path.cwd()),
                "config_file": "devservers.yml",
            }
            click.echo(f"📁 Registered project: {project_name}")
        except Exception as e:
            click.echo(f"⚠️  Could not load config: {e}", err=True)

    if project:
        click.echo(f"🚀 Starting servers for project: {project}")
        click.echo("   (autostart functionality coming soon)")

    try:
        start_manager()
    except KeyboardInterrupt:
        click.echo("\n⏹️  DevServer Manager stopped")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def stop():
    """Stop the DevServer Manager"""
    click.echo("⏹️  Stopping DevServer Manager...")
    click.echo("(Stop functionality coming soon)")


@cli.command()
def ui():
    """Open the web UI"""
    url = "http://localhost:7912"
    click.echo(f"🔗 Opening {url} in your browser...")
    webbrowser.open(url)

    click.echo("\nIf the manager is not running, start it with:")
    click.echo("  devservers start")
