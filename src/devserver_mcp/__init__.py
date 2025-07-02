import asyncio
import contextlib
import os
import socket
import sys
from pathlib import Path

import click

from devserver_mcp.config import load_config, resolve_config_path
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.types import Config
from devserver_mcp.utils import _cleanup_loop, configure_silent_logging, no_op_exception_handler, silence_all_output

__version__ = "0.6.0"


class DevServerMCP:
    def __init__(
        self,
        config_path: str | None = None,
        config: Config | None = None,
        port: int = 3001,
        _skip_port_check: bool = False,
    ):
        self.config = self._load_config(config_path, config)
        self.port = port

        if self.config.experimental and self.config.experimental.playwright:
            self._check_playwright_availability()

        if not _skip_port_check:
            self._check_port_availability()

        project_path = str(Path(config_path).parent) if config_path else None
        self.manager = DevServerManager(self.config, project_path)
        self.mcp = create_mcp_server(self.manager)
        self._mcp_task = None

    def _load_config(self, config_path: str | None, config: Config | None) -> Config:
        if config is not None:
            return config
        if config_path is not None:
            return load_config(config_path)
        raise ValueError("Either config_path or config must be provided")

    def _is_interactive_terminal(self) -> bool:
        if os.environ.get("CI"):
            return False
        return sys.stdout.isatty() and sys.stderr.isatty()

    def _check_playwright_availability(self):
        try:
            from devserver_mcp.playwright import PlaywrightOperator

            available, error_msg = PlaywrightOperator.check_availability()
            if not available:
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
        except ImportError:
            click.echo(
                "Error: Playwright tool is enabled but the playwright module is not installed.\n"
                "Please install Playwright package (uv add playwright && playwright install)",
                err=True,
            )
            sys.exit(1)

    def _check_port_availability(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", self.port))
        except OSError:
            click.echo(f"Error: Port {self.port} is already in use.", err=True)
            click.echo(
                "Please use a different port with the --port option or stop the service using that port.", err=True
            )
            sys.exit(1)

    async def run(self):
        configure_silent_logging()
        await self._run_mcp_only()

    async def _run_mcp_only(self):
        self._mcp_task = asyncio.create_task(
            self.mcp.run_async(
                transport="streamable-http",
                port=self.port,
                host="localhost",
            )
        )

        click.echo(f"DevServer MCP running at http://localhost:{self.port}/mcp/")
        click.echo("Press Ctrl+C to stop")

        try:
            await self._mcp_task
        except (SystemExit, KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            await self._cleanup()

    async def _cleanup(self):
        with silence_all_output():
            if self._mcp_task and not self._mcp_task.done():
                self._mcp_task.cancel()
                with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(self._mcp_task, timeout=0.5)

            await self.manager.shutdown_all()
            await asyncio.sleep(0.1)


@click.command()
@click.option(
    "--config", "-c", default="devservers.yml", help="Path to configuration file", type=click.Path(exists=False)
)
@click.option("--port", "-p", default=3001, type=int, help="Port for server")
def mcp_main(config, port):
    configure_silent_logging()
    config = resolve_config_path(config)

    try:
        mcp_server = DevServerMCP(config_path=config, port=port)
    except FileNotFoundError:
        click.echo(f"Error: Config file not found: {config}", err=True)
        click.echo(f"Looked for '{Path(config).name}' in current directory and parent directories.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error loading config: {e}", err=True)
        sys.exit(1)

    loop = asyncio.new_event_loop()
    loop.set_exception_handler(no_op_exception_handler)
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(mcp_server.run())
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup_loop(loop)


def main():
    """Main entry point that routes to either MCP server or new CLI."""
    if len(sys.argv) > 1 and sys.argv[1] in ["--config", "-c", "--port", "-p"]:
        mcp_main()
    else:
        from .cli import cli

        cli()


if __name__ == "__main__":
    main()
