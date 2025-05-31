from collections.abc import Awaitable, Callable

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


LogCallback = Callable[[str, str, str], None] | Callable[[str, str, str], Awaitable[None]]
