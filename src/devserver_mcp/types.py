from collections.abc import Awaitable, Callable
from enum import Enum

from pydantic import BaseModel


class ServerConfig(BaseModel):
    command: str
    working_dir: str = "."
    port: int
    prefix_logs: bool = True
    autostart: bool = False


class ExperimentalConfig(BaseModel):
    playwright: bool = False


class Config(BaseModel):
    servers: dict[str, ServerConfig]
    experimental: ExperimentalConfig | None = None


class ServerStatusEnum(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    EXTERNAL = "external"
    ERROR = "error"


class ServerStatus(BaseModel):
    name: str
    status: ServerStatusEnum
    port: int
    error: str | None = None
    color: str


LogCallback = Callable[[str, str, str], None] | Callable[[str, str, str], Awaitable[None]]


class OperationStatus(str, Enum):
    STARTED = "started"
    STOPPED = "stopped"
    ALREADY_RUNNING = "already_running"
    NOT_RUNNING = "not_running"
    ERROR = "error"


class ServerOperationResult(BaseModel):
    status: OperationStatus
    message: str


class LogsResult(BaseModel):
    status: str
    lines: list[str] | None = None
    count: int | None = None
    message: str | None = None
