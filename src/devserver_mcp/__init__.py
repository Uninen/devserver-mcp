import asyncio
import contextlib
import sys
from pathlib import Path

import click

from devserver_mcp.config import load_config, resolve_config_path
from devserver_mcp.manager import DevServerManager
from devserver_mcp.mcp_server import create_mcp_server
from devserver_mcp.types import Config
from devserver_mcp.ui import DevServerTUI
from devserver_mcp.utils import _cleanup_loop, configure_silent_logging, no_op_exception_handler, silence_all_output


class DevServerMCP:
    def __init__(
        self,
        config_path: str | None = None,
        config: Config | None = None,
        port: int = 3001,
    ):
        if config is not None:
            self.config = config
        elif config_path is not None:
            self.config = load_config(config_path)
        else:
            raise ValueError("Either config_path or config must be provided")
        self.manager = DevServerManager(self.config)
        self.mcp = create_mcp_server(self.manager)
        self.port = port
        self._mcp_task = None

    async def run(self):
        configure_silent_logging()

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
            await self._cleanup()

    async def _cleanup(self):
        with silence_all_output():
            if self._mcp_task and not self._mcp_task.done():
                self._mcp_task.cancel()
                with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
                    await asyncio.wait_for(self._mcp_task, timeout=0.5)

            await self.manager.shutdown_all()
            await asyncio.sleep(0.1)


@click.command()
@click.option(
    "--config", "-c", default="devserver.yml", help="Path to configuration file", type=click.Path(exists=False)
)
@click.option("--port", "-p", default=3001, type=int, help="Port for HTTP transport")
def main(config, port):
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


if __name__ == "__main__":
    main()
