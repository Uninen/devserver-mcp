from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.app import App
from textual.widgets import Label

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import ServerBox


class AppForTesting(App):
    def __init__(self, server_data, manager):
        super().__init__()
        self.server_data = server_data
        self.manager = manager

    def compose(self):
        yield ServerBox(self.server_data, self.manager)


@pytest.fixture
def sample_config():
    return Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
        }
    )


@pytest.fixture
def manager(sample_config):
    return DevServerManager(sample_config)


async def test_server_box_status_updates_after_click_start():
    config = Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
        }
    )
    manager = DevServerManager(config)

    initial_server_data = {"name": "frontend", "status": "stopped", "external_running": False, "error": None}

    manager.start_server = AsyncMock(return_value={"status": "started", "message": "Server started"})

    updated_server_data = {"name": "frontend", "status": "running", "external_running": False, "error": None}
    manager.get_all_servers = MagicMock(return_value=[updated_server_data])

    app = AppForTesting(initial_server_data, manager)
    async with app.run_test():
        box = app.query_one(ServerBox)

        assert box.server["status"] == "stopped"

        mock_event = MagicMock()

        await box.on_click(mock_event)

        manager.start_server.assert_called_once_with("frontend")

        updated_servers = manager.get_all_servers()
        assert updated_servers[0]["status"] == "running", "Manager should report server as running"

        assert box.server["status"] == "running", (
            f"Expected ServerBox internal status to be 'running' "
            f"but got '{box.server['status']}'. "
            f"ServerBox should update its internal server data after start_server is called."
        )

        status_label = box.query_one("#server-status", Label)
        expected_running_status = "[#00ff80]● Running[/#00ff80]"
        actual_status = status_label.renderable
        assert actual_status == expected_running_status, (
            f"Expected status label to be '{expected_running_status}' (running) "
            f"but got '{actual_status}' (still stopped). "
            f"ServerBox should refresh its labels after updating server data."
        )
