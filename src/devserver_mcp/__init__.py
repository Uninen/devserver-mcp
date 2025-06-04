import asyncio
import contextlib
import sys
from pathlib import Path
from typing import Literal

import click

from devserver_mcp.config import load_config, resolve_config_path
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.types import Config
from devserver_mcp.ui import DevServerTUI
from devserver_mcp.utils import _cleanup_loop, configure_silent_logging, no_op_exception_handler, silence_all_output

__version__ = "0.3.1"


class DevServerMCP:
    def __init__(
        self,
        config_path: str | None = None,
        config: Config | None = None,
        port: int = 3001,
        transport: Literal["streamable-http", "sse"] = "streamable-http",
    ):
        self.config = self._load_config(config_path, config)
        self.port = port
        self.transport = transport

        # Check for Playwright availability early if enabled
        if self.config.experimental and self.config.experimental.playwright:
            self._check_playwright_availability()

        self.manager = DevServerManager(self.config)
        self.mcp = create_mcp_server(self.manager)
        self._mcp_task = None

    def _load_config(self, config_path: str | None, config: Config | None) -> Config:
        if config is not None:
            return config
        if config_path is not None:
            return load_config(config_path)
        raise ValueError("Either config_path or config must be provided")

    def _is_interactive_terminal(self) -> bool:
        return sys.stdout.isatty() and sys.stderr.isatty()

    def _check_playwright_availability(self):
        """Check if Playwright is available when enabled in config."""
        try:
            from devserver_mcp.playwright import PlaywrightOperator

            available, error_msg = PlaywrightOperator.check_availability()
            if not available:
                # Print error message and exit
                click.echo(f"Error: {error_msg}", err=True)
                sys.exit(1)
        except ImportError:
            click.echo(
                "Error: Playwright tool is enabled but the playwright module is not installed.\n"
                "Please install Playwright package (uv add playwright && playwright install)",
                err=True,
            )
            sys.exit(1)

    async def run(self):
        configure_silent_logging()

        if not self._is_interactive_terminal():
            await self._run_headless()
            return

        await self._run_with_tui()

    async def _run_headless(self):
        with silence_all_output():
            await asyncio.sleep(0.1)

    async def _run_with_tui(self):
        self._mcp_task = asyncio.create_task(
            self.mcp.run_async(
                transport=self.transport,  # type: ignore
                port=self.port,
                host="localhost",
            )
        )

        if self.transport == "sse":
            mcp_url = f"http://localhost:{self.port}/sse/"
        else:
            mcp_url = f"http://localhost:{self.port}/mcp/"
        app = DevServerTUI(self.manager, mcp_url, transport=self.transport)

        try:
            await app.run_async()
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
@click.option("--port", "-p", default=3001, type=int, help="Port for HTTP transport")
@click.option("--sse", is_flag=True, help="Use SSE transport instead of streamable-http")
def main(config, port, sse):
    configure_silent_logging()
    config = resolve_config_path(config)

    try:
        transport = "sse" if sse else "streamable-http"
        mcp_server = DevServerMCP(config_path=config, port=port, transport=transport)
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


if __name__ == "__main__":
    main()
