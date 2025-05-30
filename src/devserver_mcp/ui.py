from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static

from .manager import DevServerManager


class ServerBox(Static):
    """A bordered box showing a single server's status."""

    def __init__(self, server: dict):
        super().__init__(classes="server-box")
        self.server = server

    def compose(self) -> ComposeResult:
        name = self.server["name"]
        status = self._format_status(self.server)
        yield Label(f"[b]{name}[/b]", id="server-name")
        yield Label(status, id="server-status")

    def _format_status(self, server: dict) -> str:
        if server["status"] == "running":
            return "[#00ff80]● Running[/#00ff80]"
        elif server["external_running"]:
            return "[#00ffff]● External[/#00ffff]"
        elif server["status"] == "error":
            return "[#ff0040]● Error[/#ff0040]"
        else:
            return "[#8000ff]● Stopped[/#8000ff]"


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
        background: #0a0a0f;
        color: #ff00ff;
    }

    #main-split {
        layout: horizontal;
        height: 1fr;
    }

    #servers-panel {
        border: solid #DF7BFF;
        border-title-color: white;
        border-title-style: bold;
        border-title-align: left;
        margin: 1 1;
        height: 1fr;
        width: 20%;
        min-width: 25;
        max-width: 35;
    }

    #logs-panel, #logs {
        border: solid #DF7BFF;
        border-title-color: white;
        border-title-style: bold;
        border-title-align: left;
        margin: 1;
        height: 1fr;
        width: 1fr;
        min-width: 40;
    }

    .server-box {
        margin-bottom: 1;
        padding: 0 1;
        color: #00ffff;
    }

    #bottom-bar {
        color: #ff0080;
        height: 2;
        padding: 0;
        dock: bottom;
        content-align: center middle;
    }
    
    RichLog {
        height: 1fr;
        background: transparent;
        color: #00ff80;
    }
    
    DataTable {
        height: 1fr;
        background: transparent;
        color: #ff00ff;
    }
    
    LogsWidget {
        background: transparent;
        padding: 1 2;
    }
        
    #server-name {
        color: #ff0080;
        text-style: bold;
    }
    
    #server-status {
        color: #00ffff;
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
            servers_panel = Vertical(id="servers-panel", classes="panel")
            servers_panel.border_title = "Dev Servers"
            with servers_panel:
                yield ServerStatusWidget(self.manager)

            logs_panel = Vertical(id="logs-panel", classes="panel")
            logs_panel.border_title = "Server Logs"
            with logs_panel:
                yield LogsWidget(self.manager)
        yield Static(f"MCP: {self.mcp_url} | Press Ctrl+C to quit", id="bottom-bar")

    def on_mount(self):
        self.title = "DevServer MCP"
        self.sub_title = "Development Server Manager"
