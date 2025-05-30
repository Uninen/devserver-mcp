from collections.abc import Awaitable, Callable

from pydantic import BaseModel


class ServerConfig(BaseModel):
    command: str
    working_dir: str = "."
    port: int
    prefix_logs: bool = True


class Config(BaseModel):
    servers: dict[str, ServerConfig]


LogCallback = Callable[[str, str, str], None] | Callable[[str, str, str], Awaitable[None]]
