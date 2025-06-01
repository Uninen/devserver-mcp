import asyncio
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.widget import Widget
from textual.widgets import Label, RichLog, Static

from .manager import DevServerManager


class ServerBox(Static):
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
        server_name = self.server["name"]
        action_taken = False

        if self.server["status"] == "stopped":
            await self.manager.start_server(server_name)
            action_taken = True
        elif self.server["status"] == "running" and not self.server["external_running"]:
            await self.manager.stop_server(server_name)
            # Add small delay to allow port to be released
            await asyncio.sleep(0.1)
            action_taken = True

        if action_taken:
            self._update_server_data()
            self._refresh_labels()

    def _update_server_data(self) -> None:
        servers = self.manager.get_all_servers()
        for server in servers:
            if server["name"] == self.server["name"]:
                self.server = server
                break

    def _refresh_labels(self) -> None:
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


class ToolBox(Static):
    def __init__(self, tool_name: str, status: str, manager: DevServerManager):
        super().__init__(classes="tool-box")
        self.tool_name = tool_name
        self.status = status
        self.manager = manager

    def compose(self) -> ComposeResult:
        yield Label(self._format_tool_with_status(), id="tool-display")

    def _get_tool_emoji(self) -> str:
        return "🔧"

    def _format_status_indicator(self) -> str:
        if self.status == "running":
            return "[#00ff80]●[/#00ff80]"
        elif self.status == "error":
            return "[#ff0040]●[/#ff0040]"
        else:
            return "[#8000ff]●[/#8000ff]"

    def _format_tool_with_status(self) -> str:
        emoji = self._get_tool_emoji()
        status_indicator = self._format_status_indicator()
        return f"{emoji} [b]{self.tool_name}[/b] {status_indicator}"

    def update_status(self, new_status: str):
        self.status = new_status
        try:
            tool_label = self.query_one("#tool-display", Label)
            tool_label.update(self._format_tool_with_status())
        except Exception:
            pass


class ServerStatusWidget(Widget):
    def __init__(self, manager: DevServerManager):
        super().__init__()
        self.manager = manager
        self.manager.add_status_callback(self.refresh_boxes)

    def compose(self) -> ComposeResult:
        servers = self.manager.get_all_servers()
        for server in servers:
            yield ServerBox(server, self.manager)

        # Add Playwright tool box if enabled
        if self.manager.playwright_enabled:
            status = "running" if self.manager.playwright_running else "stopped"
            yield ToolBox("Playwright", status, self.manager)

    def refresh_boxes(self):
        updated_servers_data = self.manager.get_all_servers()
        server_data_map = {s_data["name"]: s_data for s_data in updated_servers_data}

        for server_box in self.query(ServerBox):
            current_server_name = server_box.server["name"]
            if current_server_name in server_data_map:
                server_box.server = server_data_map[current_server_name]
                server_box._refresh_labels()

        # Update Playwright tool box status
        for tool_box in self.query(ToolBox):
            if tool_box.tool_name == "Playwright":
                new_status = "running" if self.manager.playwright_running else "stopped"
                tool_box.update_status(new_status)

        self.refresh()


class LogsWidget(Widget):
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
            # special handling for MCP Server
            color = "bright_white" if server == "MCP Server" else process.color if process else "white"
            formatted_message = f"[dim]{timestamp}[/dim] [{color}]{server}[/{color}] | {message}"
        else:
            # if server or timestamp is empty, the message is used as-is
            formatted_message = message
        log.write(formatted_message)


class DevServerTUI(App):
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

    .tool-box {
        margin-bottom: 0;
        padding: 0 1;
        color: #00ffff;
        background: transparent;
        border: round #333;
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
    
    #tool-display {
        color: #ff8000;
        text-style: bold;
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
            if self.manager.playwright_enabled:
                servers_panel.border_title = "Dev Servers & Tools"
            else:
                servers_panel.border_title = "Dev Servers"
            with servers_panel:
                yield ServerStatusWidget(self.manager)

            logs_panel = Vertical(id="logs-panel", classes="panel")
            logs_panel.border_title = "Server Logs"
            with logs_panel:
                yield LogsWidget(self.manager)
        yield Static(f"MCP: {self.mcp_url} | Press Ctrl+C to quit", id="bottom-bar")

    async def on_mount(self):
        self.title = "DevServer MCP"
        self.sub_title = "Development Server Manager"

        await self.manager._notify_log(
            "MCP Server",
            datetime.now().strftime("%H:%M:%S"),
            f"MCP Server started at {self.mcp_url} (streamable-http transport)",
        )

        await self.manager.autostart_configured_servers()
