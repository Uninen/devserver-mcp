import asyncio
import os
import signal
import socket
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import click
import nest_asyncio
import yaml
from fastmcp import FastMCP
from pydantic import BaseModel
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Apply nest_asyncio early to handle nested event loops
nest_asyncio.apply()

# Color palette for different servers
SERVER_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "red", "bright_cyan", "bright_magenta", "bright_yellow"]


class ServerConfig(BaseModel):
    """Configuration for a single server"""

    command: str
    working_dir: str = "."
    port: int


class Config(BaseModel):
    """Overall configuration"""

    servers: dict[str, ServerConfig]


class ManagedProcess:
    """Represents a process managed by the MCP server"""

    def __init__(self, name: str, config: ServerConfig, color: str):
        self.name = name
        self.config = config
        self.color = color
        self.process: asyncio.subprocess.Process | None = None
        self.logs: deque = deque(maxlen=500)
        self.start_time: float | None = None
        self.error: str | None = None

    async def start(self, log_callback):
        """Start the managed process"""
        try:
            self.error = None
            self.start_time = time.time()

            # Expand working directory
            work_dir = os.path.expanduser(self.config.working_dir)
            work_dir = os.path.abspath(work_dir)

            # Create subprocess
            self.process = await asyncio.create_subprocess_shell(
                self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=work_dir,
                preexec_fn=os.setsid if sys.platform != "win32" else None,
            )

            # Start reading output
            asyncio.create_task(self._read_output(log_callback))

            # Give it a moment to potentially fail
            await asyncio.sleep(0.5)

            # Check if it's still running
            if self.process.returncode is not None:
                self.error = f"Process exited immediately with code {self.process.returncode}"
                return False

            return True

        except Exception as e:
            self.error = str(e)
            return False

    async def _read_output(self, log_callback):
        """Read process output and forward to callback"""
        while self.process and self.process.stdout:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break

                decoded = line.decode("utf-8", errors="replace").rstrip()
                if decoded:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    formatted = f"{timestamp} {self.name} | {decoded}"

                    self.logs.append(decoded)
                    await log_callback(formatted, self.color)

            except Exception:
                break

    async def stop(self):
        """Stop the managed process"""
        if self.process:
            try:
                if sys.platform == "win32":
                    self.process.terminate()
                else:
                    # Kill the entire process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

                await asyncio.sleep(0.5)

                if self.process.returncode is None:
                    self.process.kill()

            except ProcessLookupError:
                pass

            self.process = None
            self.start_time = None

    @property
    def is_running(self):
        return self.process is not None and self.process.returncode is None

    @property
    def uptime(self):
        if not self.is_running or not self.start_time:
            return None
        return int(time.time() - self.start_time)


class DevServerMCP:
    """Main MCP Server implementation"""

    def __init__(self, config_path: str):
        self.console = Console()
        self.config = self._load_config(config_path)
        self.processes: dict[str, ManagedProcess] = {}
        self.output_lines: deque = deque(maxlen=1000)
        self.mcp = FastMCP("devserver")
        self._setup_tools()
        self._assign_colors()

    def _load_config(self, config_path: str) -> Config:
        """Load configuration from YAML file"""
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        return Config(**data)

    def _assign_colors(self):
        """Assign colors to servers"""
        for i, name in enumerate(self.config.servers.keys()):
            color = SERVER_COLORS[i % len(SERVER_COLORS)]
            config = self.config.servers[name]
            self.processes[name.lower()] = ManagedProcess(name, config, color)

    def _setup_tools(self):
        """Setup MCP tools"""

        @self.mcp.tool()
        async def start_server(name: str) -> dict:
            """Start a configured development server

            Args:
                name: Name of the server to start (from config)

            Returns:
                dict with status and message
            """
            process = self.processes.get(name.lower())
            if not process:
                return {"status": "error", "message": f"Server '{name}' not found in configuration"}

            if process.is_running:
                return {"status": "already_running", "message": f"Server '{name}' is already running"}

            # Check if port is already in use
            if self._is_port_in_use(process.config.port):
                return {
                    "status": "error",
                    "message": f"Port {process.config.port} is already in use by another process",
                }

            success = await process.start(self._add_output_line)

            if success:
                return {"status": "started", "message": f"Server '{name}' started successfully"}
            else:
                return {"status": "error", "message": f"Failed to start server '{name}': {process.error}"}

        @self.mcp.tool()
        async def stop_server(name: str) -> dict:
            """Stop a running server (managed or external)

            Args:
                name: Name of the server to stop

            Returns:
                dict with status and message
            """
            process = self.processes.get(name.lower())
            if not process:
                return {"status": "error", "message": f"Server '{name}' not found in configuration"}

            if process.is_running:
                await process.stop()
                return {"status": "stopped", "message": f"Server '{name}' stopped"}

            # Check for external process
            if self._is_port_in_use(process.config.port):
                # Try to kill external process on port
                if self._kill_port_process(process.config.port):
                    return {
                        "status": "stopped",
                        "message": f"External process on port {process.config.port} terminated",
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"Failed to stop external process on port {process.config.port}",
                    }

            return {"status": "not_running", "message": f"Server '{name}' is not running"}

        @self.mcp.tool()
        async def get_server_status(name: str) -> dict:
            """Get the status of a server

            Args:
                name: Name of the server to check

            Returns:
                dict with server status information
            """
            process = self.processes.get(name.lower())
            if not process:
                return {"status": "error", "message": f"Server '{name}' not found in configuration"}

            if process.is_running:
                return {
                    "status": "running",
                    "type": "managed",
                    "port": process.config.port,
                    "uptime_seconds": process.uptime,
                    "command": process.config.command,
                    "working_dir": process.config.working_dir,
                }
            elif self._is_port_in_use(process.config.port):
                return {
                    "status": "running",
                    "type": "external",
                    "port": process.config.port,
                    "message": "External process detected on configured port",
                }
            else:
                return {"status": "stopped", "type": "none", "port": process.config.port, "error": process.error}

        @self.mcp.tool()
        async def get_server_logs(name: str, lines: int = 500) -> dict:
            """Get recent log output from a managed server

            Args:
                name: Name of the server
                lines: Number of recent lines to return (max 500)

            Returns:
                dict with logs or error message
            """
            process = self.processes.get(name.lower())
            if not process:
                return {"status": "error", "message": f"Server '{name}' not found in configuration"}

            if not process.is_running:
                if self._is_port_in_use(process.config.port):
                    return {"status": "error", "message": "Cannot access logs for external process"}
                else:
                    return {"status": "error", "message": "Server is not running"}

            log_lines = list(process.logs)[-lines:]
            return {"status": "success", "lines": log_lines, "count": len(log_lines)}

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) == 0

    def _kill_port_process(self, port: int) -> bool:
        """Attempt to kill process using a port"""
        try:
            # This is platform-specific
            if sys.platform == "darwin" or sys.platform.startswith("linux"):
                import subprocess

                result = subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, capture_output=True)
                return result.returncode == 0
            else:
                # Windows would need different approach
                return False
        except Exception:
            return False

    async def _add_output_line(self, line: str, color: str):
        """Add a line to the output buffer"""
        self.output_lines.append((line, color))

    def _create_layout(self) -> Layout:
        """Create the TUI layout"""
        layout = Layout()

        # Main output area
        output_text = Text()
        for line, color in list(self.output_lines)[-50:]:  # Show last 50 lines
            output_text.append(line + "\n", style=color)

        output_panel = Panel(output_text, title="[bold]Server Output[/bold]", border_style="blue")

        # Status bar
        status_table = Table(show_header=False, box=None, expand=True)
        status_table.add_column("Server", style="bold")
        status_table.add_column("Status")
        status_table.add_column("Port")
        status_table.add_column("Uptime/Error")

        for _name, process in self.processes.items():
            if process.is_running:
                status = Text("● Running", style="green")
                uptime = f"{process.uptime}s" if process.uptime else "0s"
                info = Text(uptime, style="dim")
            elif self._is_port_in_use(process.config.port):
                status = Text("● External", style="yellow")
                info = Text("External process", style="dim yellow")
            elif process.error:
                status = Text("● Error", style="red")
                info = Text(process.error[:30] + "..." if len(process.error) > 30 else process.error, style="red")
            else:
                status = Text("● Stopped", style="dim")
                info = Text("-", style="dim")

            status_table.add_row(
                Text(process.name, style=process.color), status, Text(str(process.config.port), style="dim"), info
            )

        status_panel = Panel(
            Align.center(status_table),
            height=len(self.processes) + 2,
            title="[bold]Server Status[/bold]",
            border_style="green",
        )

        # Compose layout
        layout.split_column(
            Layout(output_panel, name="output"), Layout(status_panel, name="status", size=len(self.processes) + 2)
        )

        return layout

    async def run(self):
        """Run the MCP server with TUI"""

        # Setup signal handlers
        def signal_handler(sig, frame):
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start MCP server
        mcp_task = asyncio.create_task(self.mcp.run_async())

        # Start TUI update loop
        with Live(self._create_layout(), console=self.console, screen=True, refresh_per_second=2) as live:
            try:
                while True:
                    live.update(self._create_layout())
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                pass

        await mcp_task

    async def shutdown(self):
        """Shutdown all managed processes"""
        self.console.print("\n[yellow]Shutting down...[/yellow]")

        # Stop all processes
        tasks = []
        for process in self.processes.values():
            if process.is_running:
                tasks.append(process.stop())

        if tasks:
            await asyncio.gather(*tasks)

        # Stop the event loop
        asyncio.get_event_loop().stop()


@click.command()
@click.option(
    "--config", "-c", default="devserver.yml", help="Path to configuration file", type=click.Path(exists=False)
)
def main(config):
    """DevServer MCP - Development Server Manager"""
    # Look for config in current directory if not absolute path
    if not os.path.isabs(config) and not os.path.exists(config):
        # Try current directory
        cwd_config = Path.cwd() / config
        if cwd_config.exists():
            config = str(cwd_config)
        else:
            # Try parent directories up to git root
            current = Path.cwd()
            while current != current.parent:
                test_path = current / config
                if test_path.exists():
                    config = str(test_path)
                    break
                if (current / ".git").exists():
                    break
                current = current.parent

    try:
        server = DevServerMCP(config)
        asyncio.run(server.run())

    except FileNotFoundError:
        click.echo(f"Error: Configuration file '{config}' not found", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
