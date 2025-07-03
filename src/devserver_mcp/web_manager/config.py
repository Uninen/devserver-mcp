from dataclasses import dataclass
from pathlib import Path


@dataclass
class ManagerConfig:
    """Configuration for the DevServer Manager."""

    port: int = 7912
    host: str = "127.0.0.1"
    config_dir: Path = Path.home() / ".devserver-mcp"

    @property
    def config_file_path(self) -> Path:
        """Get the path to the global config file."""
        return self.config_dir / "config.yml"

    @property
    def status_file_path(self) -> Path:
        """Get the path to the status file."""
        return self.config_dir / "status.json"

    def ensure_config_dir(self) -> None:
        """Ensure the config directory exists."""
        self.config_dir.mkdir(exist_ok=True)
