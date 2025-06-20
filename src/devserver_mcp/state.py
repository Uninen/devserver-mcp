import hashlib
import json
import os
from pathlib import Path


class StateManager:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.state_dir = Path.home() / ".devserver-mcp"
        self.state_dir.mkdir(exist_ok=True)

        project_hash = hashlib.sha256(project_path.encode()).hexdigest()[:8]
        self.state_file = self.state_dir / f"{project_hash}_processes.json"

        self._ensure_state_file()

    def _ensure_state_file(self) -> None:
        if not self.state_file.exists():
            self._write_state({})

    def _read_state(self) -> dict[str, int]:
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _write_state(self, state: dict[str, int]) -> None:
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)

    def save_pid(self, service_name: str, pid: int) -> None:
        state = self._read_state()
        state[service_name] = pid
        self._write_state(state)

    def get_pid(self, service_name: str) -> int | None:
        state = self._read_state()
        return state.get(service_name)

    def clear_pid(self, service_name: str) -> None:
        state = self._read_state()
        state.pop(service_name, None)
        self._write_state(state)

    def cleanup_dead(self) -> None:
        state = self._read_state()
        dead_services = []

        for service_name, pid in state.items():
            if not self._is_process_alive(pid):
                dead_services.append(service_name)

        for service_name in dead_services:
            state.pop(service_name)

        if dead_services:
            self._write_state(state)

    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
