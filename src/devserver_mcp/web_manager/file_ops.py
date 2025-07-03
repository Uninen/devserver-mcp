import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import HTTPException

from devserver_mcp.web_manager.config import ManagerConfig

logger = logging.getLogger(__name__)


class FileOperations:
    """Handle all file I/O operations for the DevServer Manager."""

    def __init__(self, config: ManagerConfig):
        self.config = config

    def load_config_file(self) -> dict[str, Any]:
        """Load configuration from the config file."""
        try:
            config_file = self.config.config_file_path
            if not config_file.exists():
                return {}

            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            return {}
        except PermissionError:
            logger.error("Permission denied accessing configuration file")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            return {}

    def save_config_file(self, data: dict[str, Any]) -> None:
        """Save configuration to the config file."""
        try:
            self.config.ensure_config_dir()
            config_file = self.config.config_file_path

            # Load existing config or create new one
            existing_data = {}
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        existing_data = yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse existing config, creating new one: {e}")
                    existing_data = {}
                except Exception as e:
                    logger.warning(f"Failed to read existing config, creating new one: {e}")
                    existing_data = {}

            # Merge with existing data
            existing_data.update(data)

            # Save back to file
            with open(config_file, "w") as f:
                yaml.dump(existing_data, f, default_flow_style=False, sort_keys=False)

        except PermissionError:
            logger.error("Permission denied saving configuration. Projects will not persist.")
            raise HTTPException(
                status_code=500, detail="Unable to save configuration. Please check file permissions."
            ) from None
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise HTTPException(status_code=500, detail="Failed to save configuration. Please try again.") from e

    def write_status_file(self, running: bool, bearer_token: str | None = None) -> None:
        """Write status file for service discovery."""
        try:
            self.config.ensure_config_dir()
            status_file = self.config.status_file_path

            if running:
                status = {
                    "running": True,
                    "pid": os.getpid(),
                    "url": f"http://{self.config.host}:{self.config.port}",
                    "started_at": datetime.utcnow().isoformat() + "Z",
                    "bearer_token": bearer_token,
                }
            else:
                status = {"running": False}

            # Ensure file has restricted permissions (user read/write only)
            with open(status_file, "w") as f:
                json.dump(status, f, indent=2)

            # Set permissions to 0600 (user read/write only)
            os.chmod(status_file, 0o600)
        except PermissionError:
            logger.error("Permission denied writing status file. Service discovery may not work.")
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")

    def validate_project_path(self, path: str) -> Path:
        """Validate that a project path is safe and within allowed directories."""
        try:
            # Convert to Path and resolve to absolute path
            project_path = Path(path).resolve()

            # Ensure the path is absolute
            if not project_path.is_absolute():
                raise ValueError("Project path must be absolute")

            # Get user's home directory
            home_dir = Path.home()

            # Check if path is within user's home directory or a subdirectory
            try:
                project_path.relative_to(home_dir)
            except ValueError:
                # Allow paths outside home if they're still safe (e.g., /tmp for testing)
                # But ensure they don't contain dangerous patterns
                path_str = str(project_path)
                dangerous_patterns = ["../", "..", "~", "${", "$(", "`"]
                if any(pattern in path_str for pattern in dangerous_patterns):
                    raise ValueError("Path contains potentially dangerous patterns") from None

            # Ensure the path exists and is a directory
            if not project_path.exists():
                raise ValueError(f"Path does not exist: {project_path}")
            if not project_path.is_dir():
                raise ValueError(f"Path is not a directory: {project_path}")

            return project_path
        except Exception as e:
            raise ValueError(f"Invalid project path: {str(e)}") from e

    def get_safe_config_path(self, project_path: str, config_file: str) -> Path:
        """Safely construct a config file path, preventing directory traversal."""
        # Validate the project path first
        base_path = Path(project_path).resolve()

        # Ensure config filename doesn't contain path separators or dangerous patterns
        if "/" in config_file or "\\" in config_file or ".." in config_file:
            raise ValueError("Invalid config file name")

        # Construct the full path and resolve it
        config_path = (base_path / config_file).resolve()

        # Ensure the resolved path is still within the project directory
        try:
            config_path.relative_to(base_path)
        except ValueError:
            raise ValueError("Config file path escapes project directory") from None

        return config_path
