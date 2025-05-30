import asyncio
import contextlib
import os
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml
from fastmcp import FastMCP

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config
from devserver_mcp.ui import DevServerTUI
from devserver_mcp.utils import configure_silent_logging, no_op_exception_handler, silence_all_output


def create_mcp_server(manager: DevServerManager) -> FastMCP:
    mcp = FastMCP("devserver")

    async def start_server_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'start_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.start_server(name)

    async def stop_server_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'stop_server' called with: {{'name': {repr(name)}}}",
        )
        return await manager.stop_server(name)

    async def get_server_status_with_logging(name: str) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_status' called with: {{'name': {repr(name)}}}",
        )
        return manager.get_server_status(name)

    async def get_server_logs_with_logging(name: str, lines: int = 500) -> dict:
        await manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"Tool 'get_server_logs' called with: {{'name': {repr(name)}, 'lines': {lines}}}",
        )
        return manager.get_server_logs(name, lines)

    mcp.add_tool(start_server_with_logging, name="start_server")
    mcp.add_tool(stop_server_with_logging, name="stop_server")
    mcp.add_tool(get_server_status_with_logging, name="get_server_status")
    mcp.add_tool(get_server_logs_with_logging, name="get_server_logs")

    return mcp


def resolve_config_path(config_path: str) -> str:
    try:
        if os.path.isabs(config_path) or os.path.exists(config_path):
            return config_path

        try:
            cwd = Path.cwd()
            cwd_config = cwd / config_path
            if cwd_config.exists():
                return str(cwd_config)
        except (OSError, PermissionError):
            try:
                cwd = Path.cwd().resolve()
            except (OSError, PermissionError):
                return config_path

        current = cwd
        max_depth = 20  # Prevent infinite loops in case of symlink cycles
        depth = 0

        while current != current.parent and depth < max_depth:
            try:
                test_path = current / config_path
                if test_path.exists():
                    return str(test_path)

                git_dir = current / ".git"
                if git_dir.exists():
                    break

            except (OSError, PermissionError):
                pass

            current = current.parent
            depth += 1

    except Exception:
        pass

    return config_path


def load_config(config_path: str) -> Config:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    return Config(**data)


class DevServerMCP:
    """MCP Server integration with TUI"""

    def __init__(
        self,
        config_path: str | None = None,
        config: Config | None = None,
        port: int = 3001,
    ):
        if config is not None:
            self.config = config
        elif config_path is not None:
            loaded = load_config(config_path)
            self.config = loaded
        else:
            raise ValueError("Either config_path or config must be provided")
        self.manager = DevServerManager(self.config)
        self.mcp = create_mcp_server(self.manager)
        self.port = port
        self._shutdown_event = asyncio.Event()
        self._mcp_task = None

    async def run(self):
        configure_silent_logging()

        # Workaround for tests
        if not (sys.stdout.isatty() and sys.stderr.isatty()):
            with silence_all_output():
                await asyncio.sleep(0.1)
            return

        self._mcp_task = asyncio.create_task(
            self.mcp.run_async(transport="streamable-http", port=self.port, host="localhost")
        )

        mcp_url = f"http://localhost:{self.port}/mcp/"

        app = DevServerTUI(self.manager, mcp_url)

        try:
            await app.run_async()
        except (SystemExit, KeyboardInterrupt, asyncio.CancelledError):
            pass
        except Exception:
            pass
        finally:
            with silence_all_output():
                # Cancel MCP task gracefully
                if self._mcp_task and not self._mcp_task.done():
                    self._mcp_task.cancel()
                    with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                        await asyncio.wait_for(self._mcp_task, timeout=0.5)

                # Shutdown all managed processes
                await self.manager.shutdown_all()

                # Give a moment for cleanup
                await asyncio.sleep(0.1)


@click.command()
@click.option(
    "--config", "-c", default="devserver.yml", help="Path to configuration file", type=click.Path(exists=False)
)
@click.option("--port", "-p", default=3001, type=int, help="Port for HTTP transport (ignored for stdio)")
def main(config, port):
    """DevServer MCP - Development Server Manager"""
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
        # Silently handle Ctrl+C
        pass
    finally:
        # Ensure clean shutdown
        with silence_all_output():
            # Cancel all remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Run loop briefly to handle cancellations
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

            loop.close()


if __name__ == "__main__":
    main()
