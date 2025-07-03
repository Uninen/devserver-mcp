import json
from pathlib import Path
from typing import Literal

import httpx
from fastmcp import FastMCP
from pydantic import BaseModel, Field

DEFAULT_MANAGER_URL = "http://localhost:7912"
STATUS_FILE = Path.home() / ".devserver-mcp" / "status.json"


class ServerOperationResult(BaseModel):
    status: Literal["started", "stopped", "error", "already_running", "not_running"]
    message: str


class LogLine(BaseModel):
    timestamp: str
    message: str
    source: Literal["stdout", "stderr", "system"] = "stdout"


class LogsResult(BaseModel):
    status: Literal["success", "error"]
    message: str | None = None
    lines: list[LogLine]
    count: int
    total: int
    offset: int
    has_more: bool


class Project(BaseModel):
    id: str
    name: str
    path: str
    config_file: str
    last_accessed: str | None = None


async def discover_manager() -> tuple[str | None, str | None]:
    """Discover running manager by checking status file. Returns (url, bearer_token)."""
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE) as f:
                status = json.load(f)
                if status.get("running"):
                    url = status.get("url", DEFAULT_MANAGER_URL)
                    token = status.get("bearer_token")
                    return url, token
        except Exception:
            pass
    return None, None


async def check_manager_health(url: str) -> bool:
    """Check if manager is healthy at given URL."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/health/", timeout=2.0)
            return response.status_code == 200
    except Exception:
        return False


def get_auth_headers(bearer_token: str | None) -> dict[str, str]:
    """Get authorization headers with bearer token."""
    if bearer_token:
        return {"Authorization": f"Bearer {bearer_token}"}
    return {}


async def get_current_project(manager_url: str, bearer_token: str | None) -> str | None:
    """Get project ID for current directory."""
    current_dir = Path.cwd().resolve()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{manager_url}/api/projects/", headers=get_auth_headers(bearer_token))
            if response.status_code == 200:
                projects = [Project(**p) for p in response.json()]
                for project in projects:
                    if Path(project.path).resolve() == current_dir:
                        return project.id
        except Exception:
            pass

    return None


mcp = FastMCP("devserver-mcp")


@mcp.tool(
    description="Start a development server in the current project",
    annotations={
        "title": "Start Server",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def start_server(
    name: str = Field(description="Name of the server to start (e.g., 'django', 'frontend', 'redis')"),
    project_id: str | None = Field(
        default=None, description="Optional project ID. If not provided, uses the current directory's project"
    ),
) -> ServerOperationResult:
    """
    Start a development server.

    If project_id is not provided, attempts to use the current directory's project.
    Returns an error if the manager is not running or project cannot be determined.
    """
    manager_url, bearer_token = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return ServerOperationResult(
            status="error", message="DevServer Manager is not running. Start it with 'devservers start'"
        )

    if not project_id:
        project_id = await get_current_project(manager_url, bearer_token)
        if not project_id:
            return ServerOperationResult(
                status="error",
                message="No project found for current directory. Run 'devservers' in a project directory first",
            )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{manager_url}/api/projects/{project_id}/servers/{name}/start/",
                json={"project_id": project_id},
                headers=get_auth_headers(bearer_token),
            )
            return ServerOperationResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return ServerOperationResult(status="error", message=detail)
            elif e.response.status_code == 401:
                return ServerOperationResult(status="error", message="Authentication failed. Manager may need restart.")
            return ServerOperationResult(status="error", message=str(e))
        except Exception as e:
            return ServerOperationResult(status="error", message=f"Failed to start server: {str(e)}")


@mcp.tool(
    description="Stop a running development server",
    annotations={
        "title": "Stop Server",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def stop_server(
    name: str = Field(description="Name of the server to stop"),
    project_id: str | None = Field(
        default=None, description="Optional project ID. If not provided, uses the current directory's project"
    ),
) -> ServerOperationResult:
    """
    Stop a running development server.

    If project_id is not provided, attempts to use the current directory's project.
    """
    manager_url, bearer_token = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return ServerOperationResult(status="error", message="DevServer Manager is not running")

    if not project_id:
        project_id = await get_current_project(manager_url, bearer_token)
        if not project_id:
            return ServerOperationResult(status="error", message="No project found for current directory")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{manager_url}/api/projects/{project_id}/servers/{name}/stop/", headers=get_auth_headers(bearer_token)
            )
            return ServerOperationResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return ServerOperationResult(status="error", message=detail)
            elif e.response.status_code == 401:
                return ServerOperationResult(status="error", message="Authentication failed. Manager may need restart.")
            return ServerOperationResult(status="error", message=str(e))
        except Exception as e:
            return ServerOperationResult(status="error", message=f"Failed to stop server: {str(e)}")


@mcp.tool(
    description="Get logs from a development server",
    annotations={
        "title": "Get Server Logs",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_server_logs(
    name: str = Field(description="Name of the server to get logs from"),
    project_id: str | None = Field(
        default=None, description="Optional project ID. If not provided, uses the current directory's project"
    ),
    offset: int = Field(default=0, description="Number of lines to skip from the beginning"),
    limit: int = Field(default=100, description="Maximum number of lines to return"),
) -> LogsResult:
    """
    Get logs from a development server.

    Returns the most recent log lines from the specified server.
    """
    manager_url, bearer_token = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return LogsResult(
            status="error",
            message="DevServer Manager is not running",
            lines=[],
            count=0,
            total=0,
            offset=0,
            has_more=False,
        )

    if not project_id:
        project_id = await get_current_project(manager_url, bearer_token)
        if not project_id:
            return LogsResult(
                status="error",
                message="No project found for current directory",
                lines=[],
                count=0,
                total=0,
                offset=0,
                has_more=False,
            )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{manager_url}/api/projects/{project_id}/servers/{name}/logs/",
                params={"offset": offset, "limit": limit},
                headers=get_auth_headers(bearer_token),
            )
            return LogsResult(**response.json())
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                detail = e.response.json().get("detail", "Not found")
                return LogsResult(status="error", message=detail, lines=[], count=0, total=0, offset=0, has_more=False)
            elif e.response.status_code == 401:
                return LogsResult(
                    status="error",
                    message="Authentication failed. Manager may need restart.",
                    lines=[],
                    count=0,
                    total=0,
                    offset=0,
                    has_more=False,
                )
            return LogsResult(status="error", message=str(e), lines=[], count=0, total=0, offset=0, has_more=False)
        except Exception as e:
            return LogsResult(
                status="error",
                message=f"Failed to get logs: {str(e)}",
                lines=[],
                count=0,
                total=0,
                offset=0,
                has_more=False,
            )


@mcp.tool(
    description="List all registered projects",
    annotations={
        "title": "List Projects",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def list_projects() -> list[Project] | dict[str, str]:
    """
    List all projects registered with the DevServer Manager.

    Returns a list of projects or an error message.
    """
    manager_url, bearer_token = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return {"error": "DevServer Manager is not running. Start it with 'devservers start'"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{manager_url}/api/projects/", headers=get_auth_headers(bearer_token))
            return [Project(**p) for p in response.json()]
        except Exception as e:
            return {"error": f"Failed to list projects: {str(e)}"}


class ServerInfo(BaseModel):
    name: str
    status: str
    pid: int | None
    error: str | None
    port: int
    autostart: bool
    command: str


class DevServerStatus(BaseModel):
    project_id: str
    project_name: str
    project_path: str
    servers: list[ServerInfo]


@mcp.tool(
    description="Get the status of all development servers in the current project",
    annotations={
        "title": "Get DevServer Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def get_devserver_status(
    project_id: str | None = Field(
        default=None, description="Optional project ID. If not provided, uses the current directory's project"
    ),
) -> DevServerStatus | dict[str, str]:
    """
    Get the status of all development servers in a project.

    Returns the project information and status of all configured servers.
    If project_id is not provided, attempts to use the current directory's project.
    """
    manager_url = await discover_manager()
    if not manager_url or not await check_manager_health(manager_url):
        return {"error": "DevServer Manager is not running. Start it with 'devservers start'"}

    if not project_id:
        project_id = await get_current_project(manager_url)
        if not project_id:
            return {"error": "No project found for current directory. Run 'devservers' in a project directory first"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{manager_url}/api/projects/{project_id}/servers/")
            if response.status_code == 404:
                return {"error": f"Project '{project_id}' not found"}
            response.raise_for_status()

            data = response.json()
            return DevServerStatus(
                project_id=data["project_id"],
                project_name=data["project_name"],
                project_path=data["project_path"],
                servers=[ServerInfo(**server) for server in data["servers"]],
            )
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP error: {str(e)}"}
        except Exception as e:
            return {"error": f"Failed to get server status: {str(e)}"}


def main():
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
