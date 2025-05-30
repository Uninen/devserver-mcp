import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static

from .manager import DevServerManager


class ServerBox(Static):
    """A bordered box showing a single server's status."""

    def __init__(self, server: dict, manager: DevServerManager):
        super().__init__(classes="server-box")
        self.server = server
        self.manager = manager

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

    async def on_click(self, event: Click) -> None:
        """Handle click events on the server box."""
        server_name = self.server["name"]
        action_taken = False

        if self.server["status"] == "stopped":
            # Start the server if it's stopped
            await self.manager.start_server(server_name)
            action_taken = True
        elif self.server["status"] == "running" and not self.server["external_running"]:
            # Stop the server if it's running and managed
            await self.manager.stop_server(server_name)
            # Add small delay to allow port to be released
            await asyncio.sleep(0.1)
            action_taken = True

        # Update server data and refresh display only if action was taken
        if action_taken:
            self._update_server_data()
            self._refresh_labels()

    def _update_server_data(self) -> None:
        """Update the server data from the manager."""
        servers = self.manager.get_all_servers()
        for server in servers:
            if server["name"] == self.server["name"]:
                self.server = server
                break

    def _refresh_labels(self) -> None:
        """Refresh the server name and status labels if they exist."""
        # Check if the widget has been composed and labels exist
        if not hasattr(self, "_nodes") or not self._nodes:
            return

        try:
            name_label = self.query_one("#server-name", Label)
            status_label = self.query_one("#server-status", Label)

            name_label.update(f"[b]{self.server['name']}[/b]")
            status_label.update(self._format_status(self.server))
        except Exception:
            # Labels don't exist (e.g., in tests or not yet composed)
            pass


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
            yield ServerBox(server, self.manager)

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
        log = RichLog(highlight=True, markup=True, id="server-logs", auto_scroll=True, wrap=True)
        log.can_focus = True
        yield log

    async def add_log_line(self, server: str, timestamp: str, message: str):
        log = self.query_one(RichLog)
        formatted_message: str
        if server and timestamp:  # Both server and timestamp must be present to add our prefix
            process = self.manager.processes.get(server.lower())
            color = process.color if process else "white"
            formatted_message = f"[dim]{timestamp}[/dim] [{color}]{server}[/{color}] | {message}"
        else:
            # If server or timestamp is empty, the message is used as-is
            # This assumes the message might already be prefixed by an external tool (e.g. honcho)
            # or prefixing is explicitly disabled.
            formatted_message = message
        log.write(formatted_message)


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
        margin-bottom: 0;
        padding: 0 1;
        color: #00ffff;
        background: transparent;
        border: round transparent;
    }

    .server-box:hover {
        border: round #DF7BFF;
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
        scrollbar-background: #333;
        scrollbar-color: #DF7BFF;
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

    async def action_quit(self) -> None:
        await self.manager.shutdown_all()
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
