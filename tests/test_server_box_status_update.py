from textual.app import App
from textual.widgets import Label

from devserver_mcp.manager import DevServerManager
from devserver_mcp.ui import ServerBox


class AppForTesting(App):
    def __init__(self, server_data, manager):
        super().__init__()
        self.server_data = server_data
        self.manager = manager

    def compose(self):
        yield ServerBox(self.server_data, self.manager)


async def test_server_box_status_updates_after_click_start(running_config, temp_state_dir):
    manager = DevServerManager(running_config)

    app = AppForTesting({"name": "api", "status": "stopped", "external_running": False, "error": None}, manager)

    async with app.run_test() as pilot:
        box = app.query_one(ServerBox)

        initial_status = box.query_one("#server-status", Label).renderable
        assert "[#8000ff]● Stopped[/#8000ff]" in str(initial_status)

        await pilot.click(ServerBox)
        await pilot.pause()

        box._update_server_data()
        box._refresh_labels()
        await pilot.pause()

        updated_status = box.query_one("#server-status", Label).renderable
        assert "[#00ff80]● Running[/#00ff80]" in str(updated_status)
