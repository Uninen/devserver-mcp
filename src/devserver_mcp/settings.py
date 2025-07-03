from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProjectSettings(BaseModel):
    id: str
    idle_timeout: int = 0  # 0 means never timeout


class Settings(BaseModel):
    port: int = 7912
    idle_timeout: int = 30  # Global default in minutes, 0 = never timeout
    keep_alive_on_llm_exit: bool = True
    projects: list[ProjectSettings] = Field(default_factory=list)


def load_settings() -> Settings:
    """Load settings from the global config file."""
    config_file = Path.home() / ".devserver-mcp" / "config.yml"
    if not config_file.exists():
        return Settings()

    try:
        with open(config_file) as f:
            data = yaml.safe_load(f) or {}
            settings_data = data.get("settings", {})
            return Settings(**settings_data)
    except Exception:
        return Settings()


def save_settings(settings: Settings, existing_config: dict[str, Any] | None = None) -> None:
    """Save settings to the global config file."""
    config_file = Path.home() / ".devserver-mcp" / "config.yml"
    config_file.parent.mkdir(exist_ok=True)

    # Load existing config or use provided one
    if existing_config is None:
        try:
            if config_file.exists():
                with open(config_file) as f:
                    existing_config = yaml.safe_load(f) or {}
            else:
                existing_config = {}
        except Exception:
            existing_config = {}

    # Update settings section
    existing_config["settings"] = settings.model_dump()

    # Save back to file
    with open(config_file, "w") as f:
        yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)
