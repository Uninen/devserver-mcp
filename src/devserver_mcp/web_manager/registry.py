import logging
from typing import Any

from devserver_mcp.web_manager.file_ops import FileOperations

logger = logging.getLogger(__name__)


class ProjectRegistry:
    """Registry for managing project configurations."""

    def __init__(self, file_ops: FileOperations):
        self.file_ops = file_ops
        self._projects: dict[str, Any] = {}
        self._load_projects()

    def _load_projects(self) -> None:
        """Load projects from config file."""
        try:
            data = self.file_ops.load_config_file()
            self._projects = data.get("projects", {})
        except Exception as e:
            logger.error(f"Failed to load project registry: {e}")
            self._projects = {}

    def get_all(self) -> dict[str, Any]:
        """Get all registered projects."""
        return self._projects.copy()

    def get(self, project_id: str) -> Any | None:
        """Get a specific project by ID."""
        return self._projects.get(project_id)

    def add(self, project_id: str, project_data: Any) -> None:
        """Add a new project."""
        self._projects[project_id] = project_data
        self._save_projects()

    def remove(self, project_id: str) -> bool:
        """Remove a project by ID."""
        if project_id in self._projects:
            del self._projects[project_id]
            self._save_projects()
            return True
        return False

    def exists(self, project_id: str) -> bool:
        """Check if a project exists."""
        return project_id in self._projects

    def _save_projects(self) -> None:
        """Save projects to config file."""
        self.file_ops.save_config_file({"projects": self._projects})

    def values(self) -> Any:
        """Get all project values."""
        return self._projects.values()

    def __contains__(self, project_id: str) -> bool:
        """Check if project_id is in the registry."""
        return project_id in self._projects

    def __getitem__(self, project_id: str) -> Any:
        """Get project by ID using dict-like access."""
        return self._projects[project_id]
