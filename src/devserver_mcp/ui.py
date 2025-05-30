from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static

from .manager import DevServerManager


class ServerBox(Static):
    """A bordered box showing a single server's status."""

    def __init__(self, server: dict):
        super().__init__()
        self.server = server

    def compose(self) -> ComposeResult:
        name = self.server["name"]
        status = self._format_status(self.server)
        yield Label(f"[b]{name}[/b]", id="server-name")
        yield Label(status, id="server-status")

    def _format_status(self, server: dict) -> str:
        if server["status"] == "running":
            return "[green]● Running[/green]"
        elif server["external_running"]:
            return "[cyan]● External[/cyan]"
        elif server["status"] == "error":
            return "[red]● Error[/red]"
        else:
            return "[grey]● Stopped[/grey]"


class ServerStatusWidget(Widget):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        # If update_table is replaced, update the callback in the manager
        if name == "update_table" and hasattr(self, "manager") and hasattr(self.manager, "_status_callbacks"):
            callbacks = self.manager._status_callbacks
            for i, cb in enumerate(callbacks):
                if cb == self.refresh_boxes or cb == getattr(self, "refresh_table", None):
                    callbacks[i] = value

    """Widget displaying all server boxes in a vertical list."""

    def __init__(self, manager: DevServerManager):
        super().__init__()
        self.manager = manager
        self.manager.add_status_callback(self.refresh_boxes)
        # Backward compatibility for tests
        self.refresh_table = self.refresh_boxes
        self.update_table = self.refresh_boxes

    def compose(self) -> ComposeResult:
        servers = self.manager.get_all_servers()
        for server in servers:
            yield ServerBox(server)

    def refresh_boxes(self):
        self.refresh()

    def _format_status(self, server: dict) -> str:
        if server["status"] == "running":
            return "● Running"
        elif server["external_running"]:
            return "● External"
        elif server["status"] == "error":
            return "● Error"
        else:
            return "● Stopped"

    def _format_error(self, server: dict) -> str:
        if server["status"] == "running":
            return "Running"
        elif server["external_running"]:
            return "External process"
        elif server["error"]:
            error = server["error"][:30] + "..." if server["error"] and len(server["error"]) > 30 else server["error"]
            return error
        else:
            return "-"

    def refresh_table(self):
        self.refresh_boxes()


class LogsWidget(Widget):
    """Widget displaying server logs"""

    def __init__(self, manager: DevServerManager):
        super().__init__()
        self.manager = manager
        self.manager.add_log_callback(self.add_log_line)

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True, id="server-logs")

    async def add_log_line(self, server: str, timestamp: str, message: str):
        log = self.query_one(RichLog)
        process = self.manager.processes.get(server.lower())
        color = process.color if process else "white"
        formatted = f"[dim]{timestamp}[/dim] [{color}]{server}[/{color}] | {message}"
        log.write(formatted)


class DevServerTUI(App):
    """Main Textual application"""

    CSS = """
    Screen {
        layout: vertical;
        background: #1a1a2e;
        color: #f8f8f2;
    }

    #main-split {
        layout: horizontal;
        height: 1fr;
    }

    #servers-panel, #logs-panel, #status {
        border: solid #ff00cc;
        background: #232347;
        margin: 1 1;
        padding: 1 2;
        height: 1fr;
    }

    #servers-panel {
        width: 36%;
        min-width: 28;
    }

    #logs-panel {
        width: 1fr;
        min-width: 40;
    }

    #servers-heading, #logs-heading {
        background: #232347;
        color: #ff00cc;
        padding-left: 1;
        margin-bottom: 1;
        text-style: bold;
    }

    .server-box {
        border: solid #00fff7;
        background: #181825;
        margin-bottom: 1;
        padding: 1 1;
    }

    #bottom-bar {
        background: #181825;
        color: #ff00cc;
        height: 2;
        padding: 0 2;
        dock: bottom;
        content-align: center middle;
    }
    RichLog {
        height: 1fr;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    def action_quit(self) -> None:  # type: ignore
        self.exit(0)

    def __init__(self, manager: DevServerManager, mcp_url: str):
        super().__init__()
        self.manager = manager
        self.mcp_url = mcp_url

    def compose(self) -> ComposeResult:
        with Horizontal(id="main-split"):
            with Vertical(id="servers-panel"):
                yield Label("Dev Servers", id="servers-heading")
                yield ServerStatusWidget(self.manager)
            with Vertical(id="logs-panel"):
                yield Label("Server Logs", id="logs-heading")
                yield LogsWidget(self.manager)
        yield Static(f" MCP: {self.mcp_url}   |   Press Ctrl+C to quit ", id="bottom-bar")

    def on_mount(self):
        self.title = "DevServer MCP"
        self.sub_title = "Development Server Manager"
