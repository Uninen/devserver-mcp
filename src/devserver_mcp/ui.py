from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Header, Label, RichLog

from .manager import DevServerManager


class ServerStatusWidget(Widget):
    """Widget displaying server status table"""

    def __init__(self, manager: DevServerManager):
        super().__init__()
        self.manager = manager
        self.manager.add_status_callback(self.refresh_table)

    def compose(self) -> ComposeResult:
        table = DataTable()
        table.add_columns("Server", "Status", "Port", "Error")
        yield table

    def on_mount(self):
        self.update_table()

    def update_table(self):
        table = self.query_one(DataTable)
        table.clear()

        servers = self.manager.get_all_servers()
        for server in servers:
            status_text = self._format_status(server)

            table.add_row(server["name"], status_text, str(server["port"]))

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
            error = server["error"][:30] + "..." if len(server["error"]) > 30 else server["error"]
            return error
        else:
            return "-"

    def refresh_table(self):
        self.update_table()


class LogsWidget(Widget):
    """Widget displaying server logs"""

    def __init__(self, manager: DevServerManager):
        super().__init__()
        self.manager = manager
        self.manager.add_log_callback(self.add_log_line)

    def compose(self) -> ComposeResult:
        yield RichLog(highlight=True, markup=True)

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
    }

    #logs {
        height: 1fr;
    }

    #status {
        height: auto;
        max-height: 8;
        min-height: 4;
    }

    RichLog {
        height: 1fr;
        border: solid $primary;
    }

    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    def action_quit(self) -> None:  # type: ignore
        """Clean quit action"""
        self.exit(0)

    def __init__(self, manager: DevServerManager, mcp_url: str):
        super().__init__()
        self.manager = manager
        self.mcp_url = mcp_url

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(id="logs"):
            yield Label("[bold]Server Output[/bold]")
            yield LogsWidget(self.manager)

        with Vertical(id="status"):
            yield Label(f"[bold]Server Status[/bold] | MCP: {self.mcp_url}")
            yield ServerStatusWidget(self.manager)

        yield Label("[dim italic]Press Ctrl+C to quit[/dim italic]", id="quit-label")

    def on_mount(self):
        self.title = "DevServer MCP"
        self.sub_title = "Development Server Manager"
