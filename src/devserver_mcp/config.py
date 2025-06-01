import os
from pathlib import Path

import yaml

from devserver_mcp.types import Config


def resolve_config_path(config_path: str) -> str:
    try:
        if os.path.isabs(config_path) or os.path.exists(config_path):
            return config_path

        try:
            cwd = Path.cwd()
            cwd_config = cwd / config_path
            if cwd_config.exists():
                return str(cwd_config)
        except (OSError, PermissionError):
            try:
                cwd = Path.cwd().resolve()
            except (OSError, PermissionError):
                return config_path

        current = cwd
        max_depth = 20
        depth = 0

        while current != current.parent and depth < max_depth:
            try:
                test_path = current / config_path
                if test_path.exists():
                    return str(test_path)

                git_dir = current / ".git"
                if git_dir.exists():
                    break

            except (OSError, PermissionError):
                pass

            current = current.parent
            depth += 1

    except Exception:
        pass

    return config_path


def load_config(config_path: str) -> Config:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    experimental = data.get("experimental", {})
    data["experimental_playwright"] = experimental.get("playwright", False)

    return Config(**data)
