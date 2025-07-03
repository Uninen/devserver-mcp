from devserver_mcp.web_manager.auth import generate_bearer_token
from devserver_mcp.web_manager.config import ManagerConfig
from devserver_mcp.web_manager.file_ops import FileOperations
from devserver_mcp.web_manager.interfaces import ProcessManagerProtocol, WebSocketManagerProtocol
from devserver_mcp.web_manager.registry import ProjectRegistry


class Dependencies:
    """Container for all application dependencies."""

    def __init__(
        self,
        config: ManagerConfig,
        file_ops: FileOperations,
        project_registry: ProjectRegistry,
        process_manager: ProcessManagerProtocol,
        websocket_manager: WebSocketManagerProtocol | None = None,
        bearer_token: str | None = None,
    ):
        self.config = config
        self.file_ops = file_ops
        self.project_registry = project_registry
        self.process_manager = process_manager
        self.websocket_manager = websocket_manager
        self.bearer_token = bearer_token or generate_bearer_token()


def create_dependencies(
    config: ManagerConfig | None = None,
    process_manager: ProcessManagerProtocol | None = None,
    websocket_manager: WebSocketManagerProtocol | None = None,
) -> Dependencies:
    """Create dependencies with optional overrides for testing."""
    if config is None:
        config = ManagerConfig()

    file_ops = FileOperations(config)
    project_registry = ProjectRegistry(file_ops)

    if process_manager is None:
        from devserver_mcp.web_manager.process_manager import ProcessManager

        process_manager = ProcessManager()

    return Dependencies(
        config=config,
        file_ops=file_ops,
        project_registry=project_registry,
        process_manager=process_manager,
        websocket_manager=websocket_manager,
    )
