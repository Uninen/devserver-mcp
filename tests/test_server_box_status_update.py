from unittest.mock import AsyncMock, MagicMock

import pytest
from textual.app import App
from textual.widgets import Label

from devserver_mcp.manager import DevServerManager
from devserver_mcp.types import Config, ServerConfig
from devserver_mcp.ui import ServerBox


class TestApp(App):
    """Test app to properly mount ServerBox widget"""

    def __init__(self, server_data, manager):
        super().__init__()
        self.server_data = server_data
        self.manager = manager

    def compose(self):
        yield ServerBox(self.server_data, self.manager)


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
        }
    )


@pytest.fixture
def manager(sample_config):
    """Create a manager instance for testing"""
    return DevServerManager(sample_config)


async def test_server_box_status_updates_after_click_start():
    """Test that ServerBox status updates after clicking to start a server"""
    # Create mock config and manager
    config = Config(
        servers={
            "frontend": ServerConfig(command="npm run dev", working_dir="./frontend", port=3000),
        }
    )
    manager = DevServerManager(config)

    # Initial server state - stopped
    initial_server_data = {"name": "frontend", "status": "stopped", "external_running": False, "error": None}

    # Mock the manager's start_server method to simulate successful start
    manager.start_server = AsyncMock(return_value={"status": "started", "message": "Server started"})

    # Mock get_all_servers to return updated server data after start
    updated_server_data = {"name": "frontend", "status": "running", "external_running": False, "error": None}
    manager.get_all_servers = MagicMock(return_value=[updated_server_data])

    # Create test app and run with Textual test framework
    app = TestApp(initial_server_data, manager)
    async with app.run_test():
        # Get the ServerBox widget
        box = app.query_one(ServerBox)

        # Verify initial state
        assert box.server["status"] == "stopped"

        # Create a mock click event
        mock_event = MagicMock()

        # Simulate clicking on the server box (should start the server)
        await box.on_click(mock_event)

        # Verify start_server was called
        manager.start_server.assert_called_once_with("frontend")

        # Check that the manager would now report the server as running
        updated_servers = manager.get_all_servers()
        assert updated_servers[0]["status"] == "running", "Manager should report server as running"

        # Verify that the ServerBox updated its internal server data
        assert box.server["status"] == "running", (
            f"Expected ServerBox internal status to be 'running' "
            f"but got '{box.server['status']}'. "
            f"ServerBox should update its internal server data after start_server is called."
        )

        # Verify the status label was updated in the UI
        status_label = box.query_one("#server-status", Label)
        expected_running_status = "[#00ff80]● Running[/#00ff80]"
        actual_status = status_label.renderable
        assert actual_status == expected_running_status, (
            f"Expected status label to be '{expected_running_status}' (running) "
            f"but got '{actual_status}' (still stopped). "
            f"ServerBox should refresh its labels after updating server data."
        )
